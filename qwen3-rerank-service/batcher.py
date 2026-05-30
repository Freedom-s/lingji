import asyncio
import time
from typing import Dict, Any, List
from model_engine import Qwen3VLReranker

class DynamicBatcher:
    def __init__(self, model_path: str, max_batch_size: int = 1, max_wait_time: float = 0.1):
        # max_batch_size 设为 1，因为一个 Rerank 请求内部已经包含多个 Doc，显存压力大
        self.model = Qwen3VLReranker(model_name_or_path=model_path)
        self.queue = asyncio.Queue() # 通过一个queue来做  请求缓冲 + 调度解耦 + 流量控制。这个queue的作用是，所有的请求先进队列，然后再进行统一的调度
        self.processing = False
        asyncio.create_task(self.process_loop()) # 这里只创建了一个消费者，消费者一直在从队列中拿，然后去执行

    async def rerank(self, input_data: Dict[str, Any]) -> List[float]:
        # 拿到当前的事件循环
        loop = asyncio.get_running_loop()
        # 创建一个future对象
        future = loop.create_future()
        await self.queue.put((input_data, future))
        return await future

    async def process_loop(self):
        while True:
            # 简单逻辑：每次只取一个请求进行处理
            # 因为 Rerank 的 documents 列表可能很大，合并多个请求容易 OOM
            item = await self.queue.get()
            input_data, future = item
            
            try:
                loop = asyncio.get_running_loop()
                # 扔到线程池运行
                # 不能够并行，等待多个rerank请求一同处理的原因之一：这个model没有批量处理请求的方法，所以只能1个1个的执行
                scores = await loop.run_in_executor(
                    None, 
                    lambda: self.model.process(input_data)
                )
                if not future.done():
                    future.set_result(scores)
            except Exception as e:
                if not future.done():
                    future.set_exception(e)