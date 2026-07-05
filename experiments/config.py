"""Experiment configuration: variant definitions and default parameters."""
from dataclasses import dataclass, field


@dataclass
class VariantConfig:
    """Configuration for one retrieval variant (G1-G9)."""
    name: str
    use_text_vector: bool
    use_image_vector: bool
    use_bm25: bool
    use_rrf: bool
    use_rerank: bool
    use_context_recall: bool
    per_retrieval_topk: int = 50
    rrf_k: int = 60
    rrf_topk: int = 5
    rerank_topk: int = 3
    rerank_similarity_threshold: float = 0.7
    context_recall_max_pages: int = 1
    final_topk: int = 3


VARIANTS: dict[str, VariantConfig] = {
    "G1": VariantConfig("仅文本向量",
                        use_text_vector=True, use_image_vector=False, use_bm25=False,
                        use_rrf=False, use_rerank=False, use_context_recall=False,
                        final_topk=5),
    "G2": VariantConfig("仅图片向量",
                        use_text_vector=False, use_image_vector=True, use_bm25=False,
                        use_rrf=False, use_rerank=False, use_context_recall=False,
                        final_topk=5),
    "G3": VariantConfig("仅BM25",
                        use_text_vector=False, use_image_vector=False, use_bm25=True,
                        use_rrf=False, use_rerank=False, use_context_recall=False,
                        final_topk=5),
    "G4": VariantConfig("图片+文本",
                        use_text_vector=True, use_image_vector=True, use_bm25=False,
                        use_rrf=True, use_rerank=True, use_context_recall=False,
                        final_topk=3),
    "G5": VariantConfig("图片+BM25",
                        use_text_vector=False, use_image_vector=True, use_bm25=True,
                        use_rrf=True, use_rerank=True, use_context_recall=False,
                        final_topk=3),
    "G6": VariantConfig("三路-无RRF",
                        use_text_vector=True, use_image_vector=True, use_bm25=True,
                        use_rrf=False, use_rerank=True, use_context_recall=False,
                        final_topk=5),
    "G7": VariantConfig("三路-无Rerank",
                        use_text_vector=True, use_image_vector=True, use_bm25=True,
                        use_rrf=True, use_rerank=False, use_context_recall=False,
                        final_topk=3),
    "G8": VariantConfig("三路-无上下文",
                        use_text_vector=True, use_image_vector=True, use_bm25=True,
                        use_rrf=True, use_rerank=True, use_context_recall=False,
                        final_topk=3),
    "G9": VariantConfig("PAGE-RAG完整",
                        use_text_vector=True, use_image_vector=True, use_bm25=True,
                        use_rrf=True, use_rerank=True, use_context_recall=True,
                        final_topk=3),
}

EXPERIMENT_DEFAULTS = {
    "rrf_k": 60,
    "rrf_topk": 5,
    "rerank_topk": 3,
    "rerank_similarity_threshold": 0.7,
    "per_retrieval_topk": 50,
    "context_recall_max_pages": 1,
    "agentic_max_turns": 10,
    "agentic_max_images": 5,
}
