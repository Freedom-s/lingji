# MinerU OCR 服务 Dockerfile
# 使用官方 PyTorch 镜像作为基础（包含 CUDA 环境）
FROM pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MAGIC_pdf_TYPE=ocr

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 安装 MinerU (magic-pdf)
RUN pip install --no-cache-dir magic-pdf[full] \
    && pip install --no-cache-dir loguru

# 复制应用代码
COPY app.py .
COPY minio.py .

# 创建输出目录
RUN mkdir -p /app/output

# 暴露端口
EXPOSE 8888

# 启动命令
CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "8888"]
