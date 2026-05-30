#!/bin/bash
# GPU 服务健康检查脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 服务列表
declare -A services=(
    ["Qwen3 VL Service"]="http://localhost:8000/docs"
    ["Qwen3 Rerank Service"]="http://localhost:8001/docs"
    ["MinerU OCR Service"]="http://localhost:8888/docs"
)

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}  GPU 服务健康检查${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""

# 检查 Docker 容器状态
echo -e "${YELLOW}Docker 容器状态:${NC}"
docker compose -f docker-compose-gpu-services.yml ps 2>/dev/null || echo -e "${RED}Docker Compose 未运行${NC}"
echo ""

# 检查各服务健康状态
echo -e "${YELLOW}服务健康状态:${NC}"
all_healthy=true

for service in "${!services[@]}"; do
    url="${services[$service]}"
    if curl -s -f "$url" > /dev/null 2>&1; then
        echo -e "  [$service] ${GREEN}✓ 正常${NC} ($url)"
    else
        echo -e "  [$service] ${RED}✗ 异常${NC} ($url)"
        all_healthy=false
    fi
done

echo ""

# GPU 状态
echo -e "${YELLOW}GPU 状态:${NC}"
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null | while read line; do
        echo "  GPU $line"
    done
else
    echo -e "  ${RED}nvidia-smi 不可用${NC}"
fi

echo ""
if [ "$all_healthy" = true ]; then
    echo -e "${GREEN}所有服务运行正常！${NC}"
    exit 0
else
    echo -e "${RED}部分服务异常，请检查日志${NC}"
    exit 1
fi
