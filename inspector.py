"""七彩虹主板 BIOS 版本监控脚本。

定期检查七彩虹官网 API 获取指定主板的最新 BIOS 版本，
与本地记录的版本比对，发现新版本或确认无更新时均通过
配置的方式发送通知。

ntfy 通知的优先级可通过 [NTFY] priority_new_version / priority_no_update
配置项分别设定（默认 3 / 2）。无新版本时是否发送通知由
[NOTIFICATION] notify_on_no_update 控制（默认 true）。

支持的通知方式:
    - email: 通过 SMTP 发送邮件通知
    - notify_send: 通过 Linux 桌面通知 (libnotify) 发送通知
    - ntfy: 通过 ntfy 服务推送通知（支持优先级）
    - print: 直接在终端打印
    - none: 禁用通知

使用示例:
    $ python inspector.py
"""

import logging

from config import LOG_FILE, STATE_FILE, NOTIFY_ON_NO_UPDATE, NTFY_PRIORITY_NEW, NTFY_PRIORITY_NO_UPDATE
from scraper import get_latest_bios_info
from notifier import notify

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main():
    """主流程：检查 BIOS 更新并通过配置的方式发送通知。

    将从 API 获取的最新版本与本地记录的上次版本比对，
    发现更新时发送通知并更新记录文件；无更新时根据
    notify_on_no_update 配置决定是否发送"暂无新版本"通知。

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
