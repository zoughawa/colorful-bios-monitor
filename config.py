"""配置加载模块。

从 config.ini 读取配置，导出供其他模块使用的常量。
"""

import configparser
import sys

try:
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
except (configparser.Error, FileNotFoundError) as e:
    # 此时 logging 尚未初始化，只能用 print
    print(f"错误: 配置文件 config.ini 加载失败 - {e}", file=sys.stderr)
    print("请复制 config.ini.example 为 config.ini 并填入真实配置。", file=sys.stderr)
    sys.exit(1)
