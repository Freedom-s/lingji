#!/bin/bash

# 检查AI服务状态

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$SCRIPT_DIR/pids"

echo "=========================================="
echo "    RAGFlow-Plus AI 服务状态"
echo "=========================================="
echo ""

check_service() {
    local service_name=$1
    local port=$2
    local pid_file="$PID_DIR/${service_name}.pid"

    echo -n "$service_name (端口 $port): "

    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "\033[32m● 运行中\033[0m (PID: $pid)"

            # 检查端口是否监听
            if lsof -i ":$port" > /dev/null 2>&1; then
                echo -n "  端口 $port: "
                echo -e "\033[32m● 正常\033[0m"
            else
                echo -n "  端口 $port: "
                echo -e "\033[31m✗ 未监听\033[0m"
            fi
        else
            echo -e "\033[31m✗ 已停止\033[0m (PID 文件存在但进程不存在)"
        fi
    else
        echo -e "\033[31m✗ 未启动\033[0m (无 PID 文件)"
    fi
    echo ""
}

check_service "qwen3-vl-service" 8000
check_service "qwen3-rerank-service" 8001
check_service "mineru-ocr-service" 8888

echo "=========================================="
echo ""
