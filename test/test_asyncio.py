import asyncio
from concurrent.futures import ThreadPoolExecutor # 创建一个线程池，供future对象执行，最后返回结果
import time

def thread_task(future):
    time.sleep(5) # 模拟一个计算的过程
    future.set_result(100) # 这个future对象本质上是一个共享的变量

async def sub_task():
    print("sub_task开始")
    event_loop = asyncio.get_event_loop() # 获取到当前的事件循环
    future = event_loop.create_future() # 创建一个future对象

    executor = ThreadPoolExecutor()

    event_loop.run_in_executor(executor, thread_task, future) # 让事件循环中的任务放到一个线程中去执行

    result = await future # 等待这个具体future结果的返回
    print("sub_task结束")
    return result


async def task1():
    print("task1开始")
    result = await sub_task() # 就是说这里有一个比较耗时的任务，但是我不想要事件循环在这里阻塞，所以我可以把他放到一个线程池中去执行，这样的话就可以切换到task2执行
    print("task1结束")
    return result

async def task2():
    print("task2开始")
    await asyncio.sleep(1)
    print("task2结束")
    return 200

async def main():
    result = await asyncio.gather(task1(), task2())
    print(result)

if __name__ == '__main__':
    asyncio.run(main()) # 创建事件循环，并把函数注册进去