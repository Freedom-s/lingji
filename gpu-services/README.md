# GPU 服务 Docker Compose 部署指南

## 服务概述

本目录包含三个需要 GPU 的 AI 服务，可通过 Docker Compose 一键启动：

1. **qwen3-vl-service** (端口 8000) - Qwen3-VL 视觉语言模型嵌入服务
2. **qwen3-rerank-service** (端口 8001) - Qwen3 重排序服务
3. **mineru-ocr-service** (端口 8888) - MinerU 文档解析服务

## 前置要求

### 硬件要求
- NVIDIA GPU（推荐 12GB+ 显存）
- CUDA 12.1 兼容的驱动

### 软件要求
- Docker Engine 24.0+
- Docker Compose V2
- NVIDIA Container Toolkit（用于 GPU 支持）

### 安装 NVIDIA Container Toolkit

```bash
# Ubuntu/Debian
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# 验证安装
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

## 快速开始

### 1. 创建环境变量文件（可选）

```bash
cp .env.example .env
# 根据实际情况修改 .env 中的配置
```

### 2. 一键启动所有服务

```bash
# 在项目根目录执行
docker compose -f docker-compose-gpu-services.yml up -d

# 或者使用 GPU 专用配置（如果存在）
docker compose -f docker/docker-compose_gpu.yml up -d
```

### 3. 查看服务状态

```bash
docker compose -f docker-compose-gpu-services.yml ps
```

### 4. 查看日志

```bash
# 查看所有服务日志
docker compose -f docker-compose-gpu-services.yml logs -f

# 查看特定服务日志
docker compose -f docker-compose-gpu-services.yml logs -f qwen3-vl-service
```

### 5. 停止服务

```bash
docker compose -f docker-compose-gpu-services.yml down
```

## 服务访问

启动成功后，服务将监听以下端口：

| 服务 | 端口 | API 文档 |
|------|------|---------|
| Qwen3 VL Service | 8000 | http://localhost:8000/docs |
| Qwen3 Rerank Service | 8001 | http://localhost:8001/docs |
| MinerU OCR Service | 8888 | http://localhost:8888/docs |

## 环境变量配置

### Qwen3 服务

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| MODEL_PATH | ../Qwen3-VL-* | 模型文件路径 |
| MAX_BATCH_SIZE | 1 | 批处理大小 |
| MINIO_ENDPOINT | localhost:9000 | MinIO 服务地址 |
| MINIO_USER | rag_flow | MinIO 用户名 |
| MINIO_PASSWORD | infin... | MinIO 密码 |

### MinerU OCR 服务

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| MAGIC_pdf_TYPE | ocr | PDF 解析模式 |

## 故障排查

### GPU 不可用

```bash
# 检查 GPU 状态
nvidia-smi

# 检查容器是否可以访问 GPU
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### 服务启动失败

```bash
# 查看详细日志
docker compose -f docker-compose-gpu-services.yml logs <service-name>

# 重新构建镜像
docker compose -f docker-compose-gpu-services.yml build --no-cache <service-name>
```

### 端口冲突

如果端口被占用，可以修改 `docker-compose-gpu-services.yml` 中的端口映射：

```yaml
ports:
  - "新端口:容器端口"
```

## 重新构建服务

当修改代码后，需要重新构建镜像：

```bash
# 重建所有服务
docker compose -f docker-compose-gpu-services.yml build

# 重建特定服务
docker compose -f docker-compose-gpu-services.yml build qwen3-vl-service

# 重建并启动
docker compose -f docker-compose-gpu-services.yml up -d --build
```
