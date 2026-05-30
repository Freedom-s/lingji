# 使用官方 PyTorch 镜像作为基础（包含 CUDA 环境）
FROM pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime

# 设置工作目录
WORKDIR /app

# 设置环境变量，防止 Python 生成 .pyc 文件，并允许 stdout 输出
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安装系统依赖 (如果有)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
# 使用 uvicorn 启动 FastAPI
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]