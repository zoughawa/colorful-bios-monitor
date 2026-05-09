# AGENTS.md

## Overview
Single-file Python script (`inspector.py`) that polls the Colorful (七彩虹) motherboard BIOS API for a specific board (CVN B650M GAMING FROZEN V14) and sends a notification every run — on new version with default priority, or on no-change with low priority (ntfy only).

## Running
```bash
python inspector.py
```
No dependencies beyond `requests` (`pip install requests`). No tests, no lint/typecheck config.

## Config (`config.ini`)
- `[API] url` — Colorful product download API endpoint
- `[NOTIFICATION] method` — one of: `email`, `notify_send`, `ntfy`, `print`, `none`
- `[NOTIFICATION] notify_on_no_update` — send notification when no new version (`true`/`false`, default `true`)
- Credentials live in `config.ini` (email SMTP, ntfy auth). **Do not commit secrets.**
- `config.ini.example` — template with placeholder values, safe to commit.
- `.gitignore` ignores `config.ini`, `last_bios_version.txt`, `inspector.log`. **Always clone → copy `config.ini.example` to `config.ini` → fill in real secrets.**

## ntfy features
- Supports `Priority` header (1–5). New version → 3, no update → 2. Only `ntfy` method uses priority; others ignore it.
- Priority configurable via `[NTFY] priority_new_version` and `[NTFY] priority_no_update`.

## Notification methods
| method | prerequisite |
|---|---|
| `notify_send` | `notify-send` binary (libnotify) on Linux |
| `ntfy` | ntfy server at `http://localhost:44467` (default) |
| `email` | SMTP server via starttls |
| `print` | stdout |
| `none` | silent |

## State & logging
- `last_bios_version.txt` — tracks last seen BIOS version (persisted across runs)
- `inspector.log` — append-only log (rotated manually if needed)
- First run (no state file) always triggers a notification

## Typical usage
Runs via cron daily (based on log timestamps). No dev server, no watch mode, no codegen.

## Version detection logic
Scrapes API JSON for items containing "BIOS" in title (excluding "手册"/"教程"), extracts first all-digit token >=3 chars as version number, sorts descending.
