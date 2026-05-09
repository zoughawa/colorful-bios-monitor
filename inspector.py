"""七彩虹主板 BIOS 版本监控脚本。

定期检查七彩虹官网 API 获取指定主板的最新 BIOS 版本，
与本地记录的版本比对，发现新版本或确认无更新时均通过
配置的方式发送通知。

ntfy 通知的优先级可通过 [NTFY] priority_new_version / priority_no_update
配置项分别设定（默认 3 / 2）。无新版本时是否发送通知由
[NOTIFICATION] notify_on_no_update 控制（默认 true）。

Supported notification methods:
    - email: 通过 SMTP 发送邮件通知
    - notify_send: 通过 Linux 桌面通知 (libnotify) 发送通知
    - ntfy: 通过 ntfy 服务推送通知（支持优先级）
    - print: 直接在终端打印
    - none: 禁用通知

Typical usage example:
    $ python inspector.py

Attributes:
    config: 全局配置对象，从 config.ini 加载。
    API_URL: BIOS 信息的 API 接口地址。
    STATE_FILE: 本地持久化记录最新版本的文本文件路径。
    LOG_FILE: 运行日志文件路径。
    NOTIFY_METHOD: 通知方式 (email / notify_send / ntfy / print / none)。
    SMTP_SERVER: SMTP 服务器地址。
    SMTP_PORT: SMTP 服务器端口号。
    SENDER_EMAIL: 发件人邮箱地址。
    SENDER_PASSWORD: 发件人邮箱密码/授权码。
    RECEIVER_EMAIL: 收件人邮箱地址。
"""

import base64
import configparser
import logging
import re
import subprocess
import smtplib
from email.mime.text import MIMEText

import requests

config = configparser.ConfigParser()
config.read("config.ini", encoding="utf-8")

API_URL = config.get("API", "url")
STATE_FILE = config.get("LOCAL", "state_file")
LOG_FILE = config.get("LOCAL", "log_file")
NOTIFY_METHOD = config.get("NOTIFICATION", "method")
NOTIFY_ON_NO_UPDATE = config.getboolean("NOTIFICATION", "notify_on_no_update", fallback=True)

SMTP_SERVER = config.get("EMAIL", "smtp_server")
SMTP_PORT = config.getint("EMAIL", "smtp_port")
SENDER_EMAIL = config.get("EMAIL", "sender_email")
SENDER_PASSWORD = config.get("EMAIL", "sender_password")
RECEIVER_EMAIL = config.get("EMAIL", "receiver_email")

NTFY_SERVER = config.get("NTFY", "server")
NTFY_TOPIC = config.get("NTFY", "topic")
NTFY_USERNAME = config.get("NTFY", "username", fallback="")
NTFY_PASSWORD = config.get("NTFY", "password", fallback="")
NTFY_PRIORITY_NEW = config.getint("NTFY", "priority_new_version", fallback=3)
NTFY_PRIORITY_NO_UPDATE = config.getint("NTFY", "priority_no_update", fallback=2)


def _strip_html(text):
    """去除 HTML 标签，保留段落和换行结构。

    将 <br> 和块级结束标签（</p>、</div>、</li> 等）替换为换行符，
    再移除剩余标签，既去除格式标识又不破坏原有内容结构。

    Args:
        text: 可能包含 HTML 标签的原始字符串。

    Returns:
        保留换行结构的纯文本。
    """
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(
        r"</(p|div|li|tr|h[1-6]|blockquote)>", "\n", text, flags=re.IGNORECASE
    )
    text = re.sub(r"<[^>]+>", "", text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def send_email_notification(subject, content):
    """通过 SMTP 发送邮件通知。

    使用 config.ini 中配置的 SMTP 服务器向指定收件人发送邮件。
    支持 TLS 加密连接。

    Args:
        subject: 邮件主题。
        content: 邮件正文（纯文本格式）。

    Raises:
        Exception: SMTP 连接、登录或发送过程中发生的任何异常会被捕获并记录。
    """
    try:
        msg = MIMEText(content, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        logging.info("邮件通知发送成功")
    except Exception as e:
        logging.error("邮件发送失败: %s", e)


def send_notify_send(subject, content):
    """通过 Linux notify-send 命令发送桌面通知。

    调用系统预装的 notify-send 二进制程序，向当前桌面环境
    推送原生通知弹窗。需要系统已安装 libnotify-bin 包。

    Args:
        subject: 通知标题。
        content: 通知正文内容（首尾空白会被自动去除）。

    Raises:
        FileNotFoundError: notify-send 命令不存在时被捕获。
        Exception: 子进程执行过程中发生的其他异常被捕获。
    """
    try:
        subprocess.run(
            ["notify-send", subject, content.strip()],
            check=True,
        )
        logging.info("桌面通知发送成功")
    except FileNotFoundError:
        logging.error("桌面通知发送失败: 未找到 notify-send，请安装 libnotify-bin")
    except Exception as e:
        logging.error("桌面通知发送失败: %s", e)


def _rfc2047_b64(text):
    """将文本编码为 RFC 2047 Base64 格式。

    用于在 HTTP 头中安全传递非 ASCII 字符。输出纯 ASCII 字符串，
    形如 =?UTF-8?B?5Lit5paH?=，可被支持 RFC 2047 的服务端正确解码。

    Args:
        text: 需要编码的原始 Unicode 字符串。

    Returns:
        RFC 2047 Base64 编码后的 ASCII 字符串。
    """
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"=?UTF-8?B?{encoded}?="


def send_ntfy(subject, content, priority=3):
    """通过 ntfy 服务发送推送通知。

    向 NTFY_SERVER/{NTFY_TOPIC} 发送 POST 请求，消息正文为纯文本，
    标题通过 RFC 2047 编码后放在 Title 头中传递。需要目标 ntfy 服务
    支持 RFC 2047 头值解码。

    Args:
        subject: 通知标题，可包含非 ASCII 字符。
        content: 通知正文（纯文本）。
        priority: 消息优先级，1-5（1=最低，5=最高，默认3）。

    Raises:
        Exception: HTTP 请求或 ntfy 服务错误会被捕获并记录。
    """
    try:
        auth = (NTFY_USERNAME, NTFY_PASSWORD) if NTFY_USERNAME else None
        resp = requests.post(
            f"{NTFY_SERVER}/{NTFY_TOPIC}",
            data=content.encode("utf-8"),
            headers={
                "Title": _rfc2047_b64(subject),
                "Priority": str(priority),
            },
            auth=auth,
            timeout=10,
        )
        resp.raise_for_status()
        logging.info("ntfy通知发送成功")
    except Exception as e:
        logging.error("ntfy通知发送失败: %s", e)


def send_print(subject, content):
    """直接在终端打印通知内容。

    将标题和正文用分隔线包裹后输出到标准输出。

    Args:
        subject: 通知标题。
        content: 通知正文。
    """
    print(f"\n{'=' * 50}")
    print(f"  {subject}")
    print(f"{'=' * 50}")
    print(content)
    print(f"{'=' * 50}\n")
    logging.info("终端通知打印成功")


def get_latest_bios_info():
    """查询七彩虹 API 获取最新的 BIOS 版本信息。

    从 API 获取产品下载列表，过滤出 BIOS 固件条目（排除手册和教程），
    从标题中提取版本号并排序，返回最高版本号及其完整信息。

    Returns:
        tuple[str | None, dict | None]:
            - (version, info): 找到 BIOS 条目时返回。
              version 为版本号字符串，info 为包含 title/version/
              edit_time/fileurl/content 的字典。
            - (None, None): API 请求失败或未找到 BIOS 条目时返回。
    """
    try:
        resp = requests.get(API_URL, timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logging.error("API请求失败: %s", e)
        return None, None

    bios_list = []
    for item in data:
        title = item.get("title", "")
        if "BIOS" in title and "手册" not in title and "教程" not in title:
            parts = title.split()
            version = None
            for part in parts:
                if part.isdigit() and len(part) >= 3:
                    version = part
                    break
            if version:
                bios_list.append(
                    {
                        "title": title,
                        "version": version,
                        "edit_time": item.get("edit_time", ""),
                        "fileurl": item.get("fileurl", ""),
                        "content": _strip_html(item.get("content", "")),
                    }
                )

    if not bios_list:
        logging.warning("未找到BIOS条目")
        return None, None

    bios_list.sort(key=lambda x: int(x["version"]), reverse=True)
    latest = bios_list[0]
    return latest["version"], latest


def notify(subject, content, priority=3):
    """根据配置的通知方式分发通知。

    读取全局 NOTIFY_METHOD 配置，将通知请求路由到对应的
    具体通知实现。支持 email、notify_send、ntfy、print、none 五种方式。

    Args:
        subject: 通知标题。
        content: 通知正文。
        priority: 消息优先级，仅 ntfy 方式生效。

    See Also:
        send_email_notification: email 方式的实际发送函数。
        send_notify_send: notify_send 方式的实际发送函数。
        send_ntfy: ntfy 方式的实际发送函数。
        send_print: print 方式的实际发送函数。
    """
    if NOTIFY_METHOD == "email":
        send_email_notification(subject, content)
    elif NOTIFY_METHOD == "notify_send":
        send_notify_send(subject, content)
    elif NOTIFY_METHOD == "ntfy":
        send_ntfy(subject, content, priority)
    elif NOTIFY_METHOD == "print":
        send_print(subject, content)
    elif NOTIFY_METHOD == "none":
        logging.info("通知已禁用（NOTIFICATION.method = none）")
    else:
        logging.warning("未知的通知方式: %s", NOTIFY_METHOD)


def main():
    """主流程：检查 BIOS 更新并通过配置的方式发送通知。

    通过 NOTIFY_ON_NO_UPDATE 配置项控制无新版本时是否通知，
    ntfy 通知优先级通过 NTFY_PRIORITY_NEW / NTFY_PRIORITY_NO_UPDATE 配置。

    工作流程：
        1. 从 API 获取最新 BIOS 版本。
        2. 从本地文件读取上次记录的版本。
        3. 比对版本：若不同则标记发现更新。
        4. 发现更新时发送通知并更新本地记录文件。
        5. 版本无变化时根据配置决定是否发送"暂无新版本"通知。

    本地记录文件不存在时（首次运行），视为新版本并触发通知。
    """
    logging.info("开始检查BIOS更新...")

    current_version, latest_info = get_latest_bios_info()
    if current_version is None:
        return

    try:
        with open(STATE_FILE, "r") as f:
            last_version = f.read().strip()
    except FileNotFoundError:
        last_version = None

    logging.info("上次版本: %s", last_version if last_version else "无记录")
    logging.info("最新版本: %s", current_version)

    if last_version != current_version:
        logging.info(">>> 发现BIOS更新！")
        subject = f"【七彩虹BIOS监控】发现新版本 {current_version}"
        content = f"""主板: CVN B650M GAMING FROZEN V14
最新BIOS版本: {current_version}
发布日期: {latest_info['edit_time']}
详情: {latest_info['content'][:200]}{'...' if len(latest_info['content']) > 200 else ''}
下载地址: {latest_info['fileurl']}"""
        logging.info("通知内容:\n%s", content)
        notify(subject, content, priority=NTFY_PRIORITY_NEW)

        with open(STATE_FILE, "w") as f:
            f.write(current_version)
    else:
        logging.info("未发现BIOS更新。")
        if NOTIFY_ON_NO_UPDATE:
            subject = "【七彩虹BIOS监控】暂无新版本"
            content = f"""主板: CVN B650M GAMING FROZEN V14
当前BIOS版本: {current_version}
状态: 暂无新版本"""
            notify(subject, content, priority=NTFY_PRIORITY_NO_UPDATE)


if __name__ == "__main__":
    main()
