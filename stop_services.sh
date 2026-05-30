#!/bin/bash

# 停止所有AI服务

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$SCRIPT_DIR/pids"

echo "=========================================="
echo "    停止 RAGFlow-Plus AI 服务"
echo "=========================================="

services=(
    "qwen3-vl-service"
    "qwen3-rerank-service"
    "mineru-ocr-service"
)

for service in "${services[@]}"; do
    pid_file="$PID_DIR/${service}.pid"

    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "停止 $service (PID: $pid)..."
            kill "$pid"
            rm -f "$pid_file"
            echo "  ✓ $service 已停止"
        else
            echo "  ⚠ $service (PID: $pid) 未运行，清理 PID 文件"
            rm -f "$pid_file"
        fi
    else
        echo "  ⚠ $service 未找到 PID 文件"
    fi
done

echo ""
echo "=========================================="
echo "    所有服务已停止"
echo "=========================================="
echo ""
