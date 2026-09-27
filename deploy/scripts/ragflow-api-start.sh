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
exec /home/user/gsl/miniconda3/envs/lingji/bin/python -m api.ragflow_server
