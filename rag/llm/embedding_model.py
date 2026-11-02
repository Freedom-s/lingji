import requests
import os
from abc import ABC
import numpy as np
from rag.utils.perf_trace import perf_span


class Base(ABC):
    def __init__(self, key, model_name):
        pass

    def encode(self, texts: list):
        raise NotImplementedError("Please implement encode method!")

    def encode_queries(self, text: str):
        raise NotImplementedError("Please implement encode method!")

class OpenAI_APIEmbed(Base):
    def __init__(self, key, model_name="qwen3-vl", base_url="http://localhost:8000/v1/embeddings"):
        if not base_url:
            raise ValueError("url cannot be None")
        if base_url.split("/")[-1] == "v1":
            base_url = os.path.join(base_url, "embeddings")
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}"
        }
        self.model_name = model_name
    def encode(self, texts: list) -> np.ndarray:
        try:
            batch_size = 4
            ress = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i: i + batch_size]
                data = {
                    "model": self.model_name,
                    "input": batch
                }
                with perf_span(
                    "embedding_request",
                    model=self.model_name,
                    batch_size=len(batch),
                ):
                    res = requests.post(self.base_url, headers=self.headers, json=data).json()
                ress.extend([d['embedding'] for d in res['data']])
            return np.array(ress)
        except Exception as e:
            return None

    def encode_queries(self, text) -> np.ndarray:
        return self.encode([text])

if __name__ == '__main__':
    embeder = OpenAI_APIEmbed(key='asdasd',model_name='qwen3-vl',base_url='http://localhost:8000/v1')
    queries = [
        "A woman playing with her dog on a beach at sunset.",
        "Pet owner training dog outdoors near water.",
        "Woman surfing on waves during a sunny day.",
        "City skyline view from a high-rise building at night."
    ]
    documents = [
        "A woman shares a joyful moment with her golden retriever on a sun-drenched beach at sunset, as the dog offers its paw in a heartwarming display of companionship and trust.",
        "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen-VL/assets/demo.jpeg"
    ]
    all_inputs = queries + documents
    embeddings = embeder.encode(all_inputs)
    if embeddings.shape[0] == 6:
        query_embeddings = embeddings[:4]
        doc_embeddings = embeddings[4:]

        # 矩阵乘法计算相似度 (Query @ Doc.T)
        similarity_scores = query_embeddings @ doc_embeddings.T
        
        print("\n--- Similarity Scores (Query x Doc) ---")
        print(similarity_scores.tolist())
        
        # 简单验证：第一条 query 和第一条 doc 应该很相似
        print(f"\nQuery 1 vs Doc 1 Score: {similarity_scores[0][0]:.4f}")
