import requests
import os
from abc import ABC
import numpy as np
from rag.utils.perf_trace import perf_span


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


class Base(ABC):
    def __init__(self, key, model_name):
        pass

    def similarity(self, query: str, documents: list):
        raise NotImplementedError("Please implement encode method!")


class OpenAI_APIRerank(Base):
    def __init__(self, key, model_name, base_url):
        if not base_url:
            raise ValueError("url cannot be None")
        if base_url.split("/")[-1] == "v1":
            base_url = os.path.join(base_url, "rerank")
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}"
        }
        self.model_name = model_name

    def similarity(self, query: str, documents: list):
        try:
            data = {
                "model": self.model_name,
                "query": query,
                "documents": documents,
            }

            with perf_span(
                "rerank_request",
                model=self.model_name,
                documents_count=len(documents),
            ):
                resp = requests.post(self.base_url, headers=self.headers, json=data)

            if resp.status_code != 200:
                return None

            res = resp.json()
            # 返回一个全是0的数组
            rank = np.zeros(len(documents), dtype=float)

            if 'results' not in res:
                return None

            for d in res["results"]:
                rank[d["index"]] = d["relevance_score"]

            return rank
        except Exception as e:
            return None


if __name__ == '__main__':
    import time

    # 测试配置
    reranker = OpenAI_APIRerank(
        key='your-api-key',
        model_name='qwen3-vl-rerank',
        base_url='http://localhost:8001/v1'
    )

    # 测试查询和文档
    query = "A woman playing with her dog on a beach at sunset."
    documents = [
        "A woman shares a joyful moment with her golden retriever on a sun-drenched beach at sunset, as the dog offers its paw in a heartwarming display of companionship and trust.",
        "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen-VL/assets/demo.jpeg",
        "A woman shares a joyful moment with her golden retriever on a sun-drenched beach at sunset, as the dog offers its paw in a heartwarming display of companionship and trust."
    ]

    print("发送 Rerank 请求...")
    print(f"Query: {query}")
    print(f"Documents: {len(documents)} 个\n")

    start = time.time()
    try:
        scores = reranker.similarity(query, documents)

        if scores is None:
            print("❌ 失败: 请求返回 None")
        else:
            print(f"✅ 成功! 耗时: {time.time() - start:.2f}s")
            print(f"\n--- 相似度分数 ---")
            for i, (doc, score) in enumerate(zip(documents, scores)):
                print(f"\n[{i}] Score: {score:.4f}")
                print(f"    文档: {doc[:80]}{'...' if len(doc) > 80 else ''}")

            # 排序结果
            sorted_indices = np.argsort(scores)[::-1]  # 降序
            print(f"\n--- 排序结果 ---")
            for rank, idx in enumerate(sorted_indices, 1):
                print(f"{rank}. 文档[{idx}] - 分数: {scores[idx]:.4f}")

    except Exception as e:
        print(f"❌ 异常: {e}")
