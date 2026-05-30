#!/bin/bash

# 一键启动三个AI服务

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 日志目录
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

# PID文件目录
PID_DIR="$SCRIPT_DIR/pids"
mkdir -p "$PID_DIR"

# 初始化conda
eval "$(conda shell.bash hook)"

echo "=========================================="
echo "    启动 RAGFlow-Plus AI 服务"
echo "=========================================="

# 1. 启动 qwen3-vl-service (端口 8000)
echo "[1/3] 启动 qwen3-vl-service (端口 8000)..."
conda activate vl-embedding
cd "$SCRIPT_DIR/qwen3-vl-service"
nohup uvicorn app:app --port 8000 > "$LOG_DIR/qwen3-vl-service.log" 2>&1 &
echo $! > "$PID_DIR/qwen3-vl-service.pid"
echo "      qwen3-vl-service 已启动，PID: $(cat $PID_DIR/qwen3-vl-service.pid)"

# 2. 启动 qwen3-rerank-service (端口 8001)
echo "[2/3] 启动 qwen3-rerank-service (端口 8001)..."
conda activate vl-rerank
cd "$SCRIPT_DIR/qwen3-rerank-service"
nohup uvicorn app:app --port 8001 > "$LOG_DIR/qwen3-rerank-service.log" 2>&1 &
echo $! > "$PID_DIR/qwen3-rerank-service.pid"
echo "      qwen3-rerank-service 已启动，PID: $(cat $PID_DIR/qwen3-rerank-service.pid)"

# 3. 启动 mineru-ocr-service (端口 8888)
echo "[3/3] 启动 mineru-ocr-service (端口 8888)..."
conda activate ocr
cd "$SCRIPT_DIR/mineru-ocr-service"
nohup python app.py > "$LOG_DIR/mineru-ocr-service.log" 2>&1 &
echo $! > "$PID_DIR/mineru-ocr-service.pid"
echo "      mineru-ocr-service 已启动，PID: $(cat $PID_DIR/mineru-ocr-service.pid)"

# 返回原目录
cd "$SCRIPT_DIR"

echo ""
echo "=========================================="
echo "    所有服务已启动！"
echo "=========================================="
echo ""
echo "查看日志："
echo "  tail -f logs/qwen3-vl-service.log"
echo "  tail -f logs/qwen3-rerank-service.log"
echo "  tail -f logs/mineru-ocr-service.log"
echo ""
echo "停止服务："
echo "  ./stop_services.sh"
echo ""
echo "查看服务状态："
echo "  ./check_services.sh"
echo ""
