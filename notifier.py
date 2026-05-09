"""通知分发模块。

支持五种通知方式：email、notify_send、ntfy、print、none。
:func:`notify` 函数根据配置的 NOTIFY_METHOD 路由到对应的发送函数。
"""

import base64
import logging
import smtplib
import subprocess
from email.mime.text import MIMEText

import requests

from config import (
    NOTIFY_METHOD,
    SMTP_SERVER,
    SMTP_PORT,
    SENDER_EMAIL,
    SENDER_PASSWORD,
    RECEIVER_EMAIL,
    NTFY_SERVER,
    NTFY_TOPIC,
    NTFY_USERNAME,
    NTFY_PASSWORD,
)


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


def send_email_notification(subject, content):
    """通过 SMTP 发送邮件通知。

    使用 config.ini 中配置的 SMTP 服务器向指定收件人发送邮件，支持 TLS 加密。

    Args:
        subject: 邮件主题。
        content: 邮件正文（纯文本格式）。
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

    需要系统已安装 libnotify-bin 包。

    Args:
        subject: 通知标题。
        content: 通知正文（首尾空白会被自动去除）。
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


def send_ntfy(subject, content, priority=3):
    """通过 ntfy 服务发送推送通知。

    向 NTFY_SERVER/{NTFY_TOPIC} 发送 POST 请求，消息正文为纯文本，
    标题通过 RFC 2047 编码后放在 Title 头中传递。

    Args:
        subject: 通知标题，可包含非 ASCII 字符。
        content: 通知正文（纯文本）。
        priority: 消息优先级，1-5（1=最低，5=最高，默认3）。
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


def notify(subject, content, priority=3):
    """根据配置的通知方式分发通知。

    读取全局 NOTIFY_METHOD 配置，将通知请求路由到对应的
    具体通知实现。priority 参数仅 ntfy 方式生效。

    Args:
        subject: 通知标题。
        content: 通知正文。
        priority: 消息优先级，仅 ntfy 方式生效。

    See Also:
        :func:`send_email_notification`
        :func:`send_notify_send`
        :func:`send_ntfy`
        :func:`send_print`
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
