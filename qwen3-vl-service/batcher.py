import asyncio
import time
from typing import List, Dict, Any, Tuple
from model_engine import Qwen3VLEmbedder  # 引用你的脚本

class DynamicBatcher:
    """
    一个batch一个batch的调用qwen3vlembedder来获取结果。
    """
    def __init__(self, model_path: str, max_batch_size: int = 16, max_wait_time: float = 0.50):
        self.model = Qwen3VLEmbedder(model_name_or_path=model_path)
        self.queue = asyncio.Queue()
        self.max_batch_size = max_batch_size
        self.max_wait_time = max_wait_time
        self.processing = False
        
        # 启动后台处理循环
        asyncio.create_task(self.process_loop())

    async def embed(self, input_data: Dict[str, Any]) -> List[float]:
        """
        接收单个请求，返回 Future 结果
        """
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        await self.queue.put((input_data, future))
        return await future

    async def process_loop(self):
        """
        后台循环：从队列积攒请求，凑够一批或超时后，送入 GPU
        """
        while True:
            batch = []
            
            # 1. 获取第一个任务（阻塞等待）
            item = await self.queue.get()
            batch.append(item)
            
            # 2. 尝试获取更多任务（凑 Batch）
            deadline = time.time() + self.max_wait_time
            while len(batch) < self.max_batch_size:
                timeout = deadline - time.time()
                if timeout <= 0:
                    break
                try:
                    # 非阻塞或短超时获取
                    item = await asyncio.wait_for(self.queue.get(), timeout=max(0, timeout))
                    batch.append(item)
                except asyncio.TimeoutError:
                    break
            
            # 3. 执行推理
            if batch:
                await self.run_inference(batch)

    async def run_inference(self, batch: List[Tuple[Dict, asyncio.Future]]):
        inputs = [item[0] for item in batch]
        futures = [item[1] for item in batch]
        
        try:
            # 你的模型 process 方法是同步的 (PyTorch)，需要在线程池中运行以防阻塞 Event Loop
            # 注意：embeddings = model.process(inputs)
            loop = asyncio.get_running_loop()
            
            # 使用 run_in_executor 将计算密集型任务扔到线程池
            embeddings = await loop.run_in_executor(
                None, 
                lambda: self.model.process(inputs)
            )
            
            # 将 Tensor 转换为 list 并回填结果
            embeddings_list = embeddings.tolist()
            for i, future in enumerate(futures):
                if not future.done(): # 这个好像是判断哪个没有做完，给哪个future对象赋值
                    future.set_result(embeddings_list[i])
                    
        except Exception as e:
            for future in futures:
                if not future.done():
                    future.set_exception(e)