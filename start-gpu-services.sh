#!/bin/bash
# GPU 服务快速启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$PROJECT_ROOT/gpu-services/.env"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose-gpu-services.yml"

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}  GPU 服务 Docker Compose 启动脚本${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: 未找到 Docker，请先安装 Docker${NC}"
    exit 1
fi

# 检查 Docker Compose 是否可用
if ! docker compose version &> /dev/null; then
    echo -e "${RED}错误: Docker Compose 不可用，请升级到 Docker 24.0+${NC}"
    exit 1
fi

# 检查 NVIDIA GPU 支持
if ! docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
    echo -e "${YELLOW}警告: NVIDIA Container Toolkit 可能未正确安装${NC}"
    echo -e "${YELLOW}如果服务启动失败，请参考 gpu-services/README.md 安装 NVIDIA Container Toolkit${NC}"
    echo ""
fi

# 创建 .env 文件（如果不存在）
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}未找到 .env 文件，从 .env.example 创建...${NC}"
    cp "$PROJECT_ROOT/gpu-services/.env.example" "$ENV_FILE"
    echo -e "${GREEN}.env 文件已创建，请根据需要修改配置${NC}"
    echo ""
fi

# 显示菜单
echo "请选择操作:"
echo "  1) 启动所有服务"
echo "  2) 停止所有服务"
echo "  3) 重启所有服务"
echo "  4) 查看服务状态"
echo "  5) 查看服务日志"
echo "  6) 重新构建并启动"
echo "  7) 清理所有服务和数据"
echo ""
read -p "请输入选项 [1-7]: " choice

case $choice in
    1)
        echo -e "${GREEN}启动所有 GPU 服务...${NC}"
        docker compose -f "$COMPOSE_FILE" up -d
        echo ""
        echo -e "${GREEN}服务已启动！${NC}"
        echo ""
        echo "服务访问地址:"
        echo "  - Qwen3 VL Service:   http://localhost:8000/docs"
        echo "  - Qwen3 Rerank Service: http://localhost:8001/docs"
        echo "  - MinerU OCR Service:  http://localhost:8888/docs"
        echo ""
        echo "查看状态: docker compose -f $COMPOSE_FILE ps"
        echo "查看日志: docker compose -f $COMPOSE_FILE logs -f"
        ;;
    2)
        echo -e "${YELLOW}停止所有 GPU 服务...${NC}"
        docker compose -f "$COMPOSE_FILE" down
        echo -e "${GREEN}服务已停止${NC}"
        ;;
    3)
        echo -e "${YELLOW}重启所有 GPU 服务...${NC}"
        docker compose -f "$COMPOSE_FILE" restart
        echo -e "${GREEN}服务已重启${NC}"
        ;;
    4)
        echo -e "${GREEN}服务状态:${NC}"
        docker compose -f "$COMPOSE_FILE" ps
        ;;
    5)
        echo -e "${GREEN}显示服务日志 (Ctrl+C 退出):${NC}"
        docker compose -f "$COMPOSE_FILE" logs -f
        ;;
    6)
        echo -e "${YELLOW}重新构建并启动服务...${NC}"
        docker compose -f "$COMPOSE_FILE" up -d --build
        echo -e "${GREEN}服务已重新构建并启动${NC}"
        ;;
    7)
        read -p "确定要删除所有服务和数据吗? (y/N): " confirm
        if [[ $confirm == [yY] ]]; then
            echo -e "${RED}删除所有服务和数据...${NC}"
            docker compose -f "$COMPOSE_FILE" down -v
            echo -e "${GREEN}已清理完成${NC}"
        else
            echo "操作已取消"
        fi
        ;;
    *)
        echo -e "${RED}无效选项${NC}"
        exit 1
        ;;
esac
