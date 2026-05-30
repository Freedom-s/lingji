import os
import asyncio
import aiohttp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import List, Union, Optional, Dict, Any
from minio import Minio
from PIL import Image
from io import BytesIO
import base64
from batcher import DynamicBatcher

# 配置
MODEL_PATH = os.getenv("MODEL_PATH", "../Qwen3-VL-Reranker-2B")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_USER", "rag_flow")
MINIO_SECRET_KEY = os.getenv("MINIO_PASSWORD", "infini_rag_flow")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
DOWNLOAD_TIMEOUT = 10

batcher: Optional[DynamicBatcher] = None
http_session: Optional[aiohttp.ClientSession] = None
minio_client: Optional[Minio] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global batcher, http_session, minio_client
    print(f"Loading Reranker model from {MODEL_PATH}...")
    # Reranker 显存占用高，建议 Batch Size 设为 1 (处理单次请求)
    batcher = DynamicBatcher(model_path=MODEL_PATH, max_batch_size=1)
    
    http_session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT),
        connector=aiohttp.TCPConnector(limit=100)
    )
    
    try:
        minio_client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )
        print("MinIO connected.")
    except Exception:
        print("MinIO init failed.")
        
    yield
    if http_session: await http_session.close()

app = FastAPI(title="Qwen3-VL-Rerank Service", lifespan=lifespan)

# --- 数据模型 ---
class InputItem(BaseModel):
    text: Optional[str] = None
    image: Optional[str] = None

class RerankRequest(BaseModel):
    """
    只有query字段和documents字段是必须填写的
    """
    model: Optional[str] = "qwen3-vl-rerank"
    query: Union[str, InputItem] 
    documents: List[Union[str, InputItem]]
    instruction: Optional[str] = "Retrieve images or text relevant to the user's query."
    fps: Optional[float] = 1.0

class RerankResponse(BaseModel):
    model: str
    results: List[Dict[str, Any]] # [{"index": 0, "relevance_score": 0.9}, ...]

# --- 工具函数 ---
def _download_minio_sync(bucket, obj_name):
    try:
        resp = minio_client.get_object(bucket, obj_name)
        data = resp.read()
        resp.close()
        return data
    except:
        return None

async def fetch_image(url: str) -> Optional[Image.Image]:
    """
    这个函数的作用就是将1.base64的图片字符串 2.minio的地址 3.线上的http地址，转化为Image类型的图片
    """

    if not url or not isinstance(url, str): return None
    img_data = None
    
    if url.startswith("data:image/"):
        try:
            _, b64 = url.split(",", 1)
            img_data = base64.b64decode(b64)
        except: pass
    elif url.startswith("minio://") and minio_client:
        try:
            path = url[8:]
            bucket, obj = path.split("/", 1)
            loop = asyncio.get_running_loop()
            img_data = await loop.run_in_executor(None, _download_minio_sync, bucket, obj)
        except: pass
    elif url.startswith(("http://", "https://")) and http_session:
        try:
            async with http_session.get(url) as resp:
                if resp.status == 200: img_data = await resp.read()
        except: pass

    if img_data:
        try:
            return Image.open(BytesIO(img_data)).convert("RGB")
        except: pass
    return None

def normalize_item(item: Union[str, InputItem]) -> Dict[str, Any]:
    """标准化为 {"text":..., "image":...} 格式"""

    # 先处理query/document只是一个普通字符串的情况；
    if isinstance(item, str):
        item = item.strip()
        if item.startswith(("http", "https", "minio", "data:image")):
            return {"image": item}
        return {"text": item}
    
    # 如果query/document传递的不只是一个字符串，那就说明他是一个字典形式的内容。
    res = {}
    if item.text: res["text"] = item.text
    if item.image: res["image"] = item.image
    return res

@app.post("/v1/rerank", response_model=RerankResponse)
async def rerank(req: RerankRequest):
    if not batcher:
        raise HTTPException(503, "Service not ready")

    # 1. 解析 Query（处理成为字典形式）
    query_dict = normalize_item(req.query)
    
    # 2. 解析 Documents（处理成为字典形式）
    docs_dict_list = [normalize_item(doc) for doc in req.documents]

    # 3. 收集所有图片下载任务
    download_tasks = [] # 这里面存放的全部都是协程对象
    
    # Query 图片
    if "image" in query_dict and isinstance(query_dict["image"], str):
        download_tasks.append(fetch_image(query_dict["image"]))
    else:
        download_tasks.append(asyncio.sleep(0)) # 占位

    # Docs 图片
    for doc in docs_dict_list:
        if "image" in doc and isinstance(doc["image"], str):
            download_tasks.append(fetch_image(doc["image"]))
        else:
            download_tasks.append(asyncio.sleep(0)) # 占位

    # 4. 并发下载（注册所有的任务函数，并等待结果返回），所有图片的情况都去返回结果，所有非图片的，其实都是none。
    results = await asyncio.gather(*download_tasks)

    # 5. 回填图片对象
    # 处理 Query
    query_img_res = results[0] # 因为一般请款下也就一个query，对应多个查询向量做的rerank
    if query_img_res:
        query_dict["image"] = query_img_res
    
    # 处理 Docs
    doc_img_results = results[1:]
    for i, img_obj in enumerate(doc_img_results):
        if img_obj:
            docs_dict_list[i]["image"] = img_obj

    # 6. 构造模型输入
    model_input = {
        "instruction": req.instruction,
        "query": query_dict,
        "documents": docs_dict_list,
        "fps": req.fps
    }
    # 7. 调用模型
    scores = await batcher.rerank(model_input)

    # 8. 格式化输出
    output_data = []
    for i, score in enumerate(scores):
        output_data.append({
            "index": i,
            "relevance_score": score
        })

    return RerankResponse(model=req.model, results=output_data)

@app.get("/health")
async def health():
    return {"status": "ok"}