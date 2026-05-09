#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CRON_ID="# colorful-bios-monitor"
CRON_CMD="cd $SCRIPT_DIR && python3 $SCRIPT_DIR/inspector.py"
usage() {
    echo "用法: $0 [cron表达式]"
    echo "示例:"
    echo "  $0                  # 每天 8:00 运行"
    echo "  $0 '*/6 * * * *'    # 每 6 小时运行"
    echo "  $0 '0 9,21 * * *'   # 每天 9:00 和 21:00 运行"
    exit 1
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
fi

SCHEDULE="${1:-0 8 * * *}"

if crontab -l 2>/dev/null | grep -qF "$CRON_ID"; then
    echo "cron 任务已存在，跳过"
    exit 0
fi

(crontab -l 2>/dev/null || true; echo "$CRON_ID"; echo "$SCHEDULE $CRON_CMD") | crontab -

echo "cron 任务已添加 ($SCHEDULE)"
