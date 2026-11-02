#!/usr/bin/env bash
set -euo pipefail
umask 077

LOG_DIR="/home/user/jianhuasuo/lingji/api/logs"
mkdir -p "$LOG_DIR"

STAMP="$(date '+%Y%m%d_%H%M%S_%N')"
LOG_FILE="$LOG_DIR/start_${STAMP}.log"
exec >>"$LOG_FILE" 2>&1

echo "===== ragflow-api started at $(date '+%Y-%m-%d %H:%M:%S %z') ====="
echo "PID=$$"

export PYTHONUNBUFFERED=1
export PYTHONPATH="/home/user/jianhuasuo/lingji"
exec /home/user/gsl/miniconda3/envs/lingji/bin/python -m gunicorn \
  --bind 0.0.0.0:9380 \
  --workers 2 \
  --worker-class gthread \
  --threads 4 \
  --timeout 3600 \
  --graceful-timeout 30 \
  --keep-alive 65 \
  --access-logfile - \
  --error-logfile - \
  --capture-output \
  api.wsgi:application
