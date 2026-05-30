import os
import json
import time
from typing import List, Union, Optional
from fastapi import FastAPI, HTTPException, Request
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
from batcher import DynamicBatcher
import asyncio
from minio import Minio
import aiohttp
from PIL import Image
from io import BytesIO
import base64
# 当前的这个服务，暂时先只考虑两种情况吧，第一种情况，直接传入文本信息，第二种情况，直接传入一个minio://xxxx类型的图片路径
# 所有的参数都有这个服务来进行构造。

# 配置
MODEL_PATH = os.getenv("MODEL_PATH", "../Qwen3-VL-Embedding-2B") # 这里放一个本地的模型记录
MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", "1")) # 这个batch尽量调小一些，因为显存不够，放到大的显卡上可以适当变大
DOWNLOAD_TIMEOUT = 10

# MinIO 配置
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000") # 不带 http://
MINIO_ACCESS_KEY = os.getenv("MINIO_USER", "rag_flow")
MINIO_SECRET_KEY = os.getenv("MINIO_PASSWORD", "infini_rag_flow")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true" # 是否使用 HTTPS

# --- 全局单例 ---
batcher: Optional[DynamicBatcher] = None
http_session: Optional[aiohttp.ClientSession] = None
minio_client: Optional[Minio] = None

app = FastAPI(title="Qwen3-VL-Embedding API")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global batcher, http_session, minio_client
    
    # 1. 加载模型
    print(f"Loading model from {MODEL_PATH}...")
    batcher = DynamicBatcher(model_path=MODEL_PATH, max_batch_size=MAX_BATCH_SIZE)
    
    # 2. 初始化 HTTP 连接池
    http_session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT), # 下载一个文件的超时时间
        connector=aiohttp.TCPConnector(limit=100) # 最多同时有100个文件进行连接
    )
    
    # 3. 初始化 MinIO 客户端
    try:
        minio_client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )
        print(f"MinIO client connected to {MINIO_ENDPOINT}")
    except Exception as e:
        print(f"Warning: Failed to init MinIO client: {e}")

    print("System ready.")
    yield
    
    if http_session:
        await http_session.close()
    print("System shutdown.")

app = FastAPI(title="Qwen3-VL-Embedding API", lifespan=lifespan)

# --- OpenAI 兼容的数据模型 ---
class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]] # 这的输入，暂时只考虑两种情况吧，一种是直接传入minio://地址的，另外一种是传入文字的
    model: Optional[str] = "qwen3-vl"
    encoding_format: Optional[str] = "float"


class EmbeddingData(BaseModel):
    object: str = "embedding"
    embedding: List[float]
    index: int

class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[EmbeddingData]
    model: str

# 从minio里面来下载一张图片
def _download_minio_sync(bucket_name: str, object_name: str) -> Optional[bytes]:
    """同步的 MinIO 下载函数，将在线程池中运行。这是一个同步阻塞的函数！！"""
    try:
        response = minio_client.get_object(bucket_name, object_name)
        data = response.read()
        response.close()
        response.release_conn()
        return data
    except Exception as e:
        print(f"MinIO download error [{bucket_name}/{object_name}]: {e}")
        return None

async def fetch_image(url: str) -> Optional[Image.Image]:
    """
    智能下载器：支持 HTTP/HTTPS 和 MinIO 自定义协议
    协议格式: minio://bucket_name/path/to/image.jpg
    """
    if not url:
        return None

    image_data = None
    if url.startswith("data:image/"):
        try:
            # 格式通常是: data:image/jpeg;base64,/9j/4AAQSk...
            # 我们需要去掉逗号前面的部分
            header, base64_str = url.split(",", 1)
            image_data = base64.b64decode(base64_str)
        except Exception as e:
            print(f"Base64 decode error: {e}")
            return None
    # CASE A: MinIO 协议 (minio://bucket/key)
    elif url.startswith("minio://"):
        if not minio_client:
            print("Error: MinIO client not initialized but received minio:// URL")
            return None
            
        # 解析 bucket 和 object_name
        # url: minio://mybucket/pages/001.jpg -> path: mybucket/pages/001.jpg
        path_without_prefix = url[8:] 
        parts = path_without_prefix.split("/", 1) # 分割为 ['mybucket','pages/001.jpg']
        if len(parts) != 2:
            print(f"Invalid MinIO URL format: {url}")
            return None
            
        bucket_name, object_name = parts[0], parts[1]
        
        # 将阻塞的 MinIO 操作扔到线程池执行，实现异步化
        loop = asyncio.get_running_loop() # 获取一个循环对象
        image_data = await loop.run_in_executor(
            None, # 使用默认的线程池
            _download_minio_sync, 
            bucket_name, 
            object_name
        )

    # CASE B: 常规 HTTP/HTTPS
    elif url.startswith(("http://", "https://")):
        if not http_session:
            return None
        try:
            async with http_session.get(url) as response:
                if response.status == 200:
                    image_data = await response.read()
                else:
                    print(f"HTTP download failed {url}: {response.status}")
        except Exception as e:
            print(f"HTTP error {url}: {e}")

    # --- 统一转图片 ---
    if image_data:
        try:
            # 转换为 RGB 格式
            return Image.open(BytesIO(image_data)).convert("RGB")
        except Exception as e:
            print(f"Image decode error: {e}")
            return None
    
    return None

# --- 核心逻辑：输入解析 ---
def normalize_input(item: Union[str, dict]) -> dict:
    """
    将任意类型的单个输入项（字符串/字典）统一转为模型可识别的字典格式。
    核心逻辑：
    1. 如果是字典，直接用。
    2. 如果是字符串，判断是否为 URL (http/minio)。
       - 是 URL -> 视为图片 {"image": url}
       - 否 -> 视为文本 {"text": str}
       - 如果是 JSON 字符串 -> 解析后递归处理
    """
    
    if isinstance(item, str):
        item_stripped = item.strip()
        
        if item_stripped.startswith(("minio://", "http://", "https://", "data:image/")):
            return {"image": item_stripped}
        # 否则归类为普通文本
        return {"text": item}
        
    res = {}
    if "text" in item: 
        res["text"] = item["text"]
    if "image" in item: 
        res["image"] = item["image"]
    return res

@app.post("/v1/embeddings", response_model=EmbeddingResponse)
async def create_embedding(request: EmbeddingRequest):
    """
    最好传递过来的情况是这种格式的
    input:[{"text":"xxx"},{"image":"xxx"},]或者他们的组合
    暂时只考虑这种情况
    .encode([xxx,xxx])
    .encode(xxx)
    """
    if not batcher:
        raise HTTPException(status_code=503, detail="Service not ready")

    # 1. 标准化输入列表
    raw_inputs = request.input
    if not isinstance(raw_inputs, list):
        # 如果不是list，我给他封装成一个list
        raw_inputs = [raw_inputs]
    
    # 2. 解析每个输入项
    parsed_inputs = [normalize_input(item) for item in raw_inputs] # 这里的raw_inputs是一个*字符串数组*！！

    # 3. 并发预下载图片
    download_tasks = []
    for item in parsed_inputs:
        img_source = item.get("image")
        
        # 检查 image 字段是否为待下载的 URL 字符串
        if isinstance(img_source, str) and (
            img_source.startswith(("http", "https", "minio", "data:image/"))
        ):
            # 触发下载图片的操作，然后转化为一个Image.Image对象
            download_tasks.append(fetch_image(img_source))
        else:
            # 不需要下载（可能是文本，或者已经是 Image 对象）
            download_tasks.append(asyncio.sleep(0, result=None)) # 一个用来占位的空携程
    
    # 执行下载
    downloaded_images = await asyncio.gather(*download_tasks)

    # 4. 组装最终输入数据
    final_inputs = []
    for i, item in enumerate(parsed_inputs):
        # 如果下载成功，用 PIL Image 对象替换原来的 URL
        if downloaded_images[i] is not None:
            item["image"] = downloaded_images[i] # 这里的item，已经是一个Image.Image对象了
        
        final_inputs.append(item)


    # 5. 提交给 Batcher 进行推理
    # asyncio.gather 保证了并发处理列表中的每一项
    embedding_futures = [batcher.embed(inp) for inp in final_inputs] # 把当前请求的所有数据全部做成协程对象。
    embeddings = await asyncio.gather(*embedding_futures)

    # 6. 构造响应
    data_objs = [
        EmbeddingData(embedding=emb, index=i) 
        for i, emb in enumerate(embeddings)
    ]

    return EmbeddingResponse(
        data=data_objs, 
        model=request.model
    )

@app.get("/health")
async def health():
    return {"status": "ok"}