#!/usr/bin/env bash
set -euo pipefail

# MyPick daily production updater.
# This script is intended to be run by systemd timer at 23:00 KST.
# It backs up the SQLite DB first, then runs scheduler.py once.

PROJECT_DIR="${MYPICK_PROJECT_DIR:-/var/www/mypick}"
PYTHON_BIN="${MYPICK_PYTHON_BIN:-$PROJECT_DIR/venv/bin/python}"
DB_PATH="${MYPICK_DB_PATH:-$PROJECT_DIR/kbo_fantasy.db}"
BACKUP_DIR="${MYPICK_BACKUP_DIR:-$PROJECT_DIR/backups}"
LOG_DIR="${MYPICK_LOG_DIR:-$PROJECT_DIR/logs}"
DATE_KST="$(TZ=Asia/Seoul date +%Y%m%d)"
STAMP_KST="$(TZ=Asia/Seoul date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR" "$LOG_DIR"

cd "$PROJECT_DIR"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "❌ Python executable not found: $PYTHON_BIN" >&2
  exit 1
fi

if [ ! -f "$DB_PATH" ]; then
  echo "❌ DB file not found: $DB_PATH" >&2
  exit 1
fi

BACKUP_FILE="$BACKUP_DIR/kbo_fantasy_before_daily_update_${STAMP_KST}.db"
LOG_FILE="$LOG_DIR/daily_update_${STAMP_KST}.log"

echo "================================================================================" | tee -a "$LOG_FILE"
echo "MyPick daily update start: $STAMP_KST KST" | tee -a "$LOG_FILE"
echo "Project: $PROJECT_DIR" | tee -a "$LOG_FILE"
echo "DB: $DB_PATH" | tee -a "$LOG_FILE"
echo "Backup: $BACKUP_FILE" | tee -a "$LOG_FILE"
echo "Target date: $DATE_KST" | tee -a "$LOG_FILE"
echo "================================================================================" | tee -a "$LOG_FILE"

cp "$DB_PATH" "$BACKUP_FILE"

echo "✅ DB backup created" | tee -a "$LOG_FILE"

# scheduler.py --run-now uses Asia/Seoul today internally.
# --date "$DATE_KST" is intentionally not used here so the app's own KST helper remains the source of truth.
"$PYTHON_BIN" scheduler.py --run-now 2>&1 | tee -a "$LOG_FILE"

echo "================================================================================" | tee -a "$LOG_FILE"
echo "MyPick daily update finished: $(TZ=Asia/Seoul date +%Y%m%d_%H%M%S) KST" | tee -a "$LOG_FILE"
echo "================================================================================" | tee -a "$LOG_FILE"

# Keep only the latest 30 DB backups and latest 60 daily logs by default.
# Remove these lines if you want to manage retention manually.
find "$BACKUP_DIR" -name 'kbo_fantasy_before_daily_update_*.db' -type f | sort | head -n -30 | xargs -r rm --
find "$LOG_DIR" -name 'daily_update_*.log' -type f | sort | head -n -60 | xargs -r rm --
