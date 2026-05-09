#!/usr/bin/env bash
set -euo pipefail

CRON_ID="# colorful-bios-monitor"

if ! crontab -l 2>/dev/null | grep -qF "$CRON_ID"; then
    echo "cron 任务不存在"
    exit 0
fi

crontab -l 2>/dev/null | sed "/$CRON_ID/{N;d;}" | crontab -

echo "cron 任务已移除"
