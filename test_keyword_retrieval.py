#!/usr/bin/env python3
"""
测试 _keyword_retrieval 函数

运行前确保：
1. 服务已启动（ES/Infinity + Redis + MySQL）
2. 有已索引的知识库数据
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from rag.nlp.search import Dealer
from api.settings import init_settings


def test_keyword_retrieval():
    """测试关键词（BM25）检索"""

    # ========== 配置参数 ==========
    question = "what is the multi-stage training pipeline of Qwen3-VL-Embedding and Qwen3-VL-Reranker?"
    tenant_id = ["f98d14dcfd1511f09ad2420839d2c59b"]
    kb_ids = ["01e9cbfe65e34b088df195a2486b0caa"]
    top_k = 50

    print("=" * 60)
    print(f"[测试] 关键词（BM25）检索")
    print(f"问题: {question}")
    print(f"租户ID: {tenant_id}")
    print(f"知识库IDs: {kb_ids}")
    print(f"Top-K: {top_k}")
    print("=" * 60)

    # ========== 1. 初始化 Settings ==========
    print("\n[1/2] 初始化 Settings...")
    try:
        init_settings()
        from api.settings import retrievaler
        dealer = retrievaler
        print(f"✓ Settings 初始化成功")
    except Exception as e:
        print(f"✗ Settings 初始化失败: {e}")
        return

    # ========== 2. 获取 Dealer 实例 ==========
    print("\n[2/2] 获取 Dealer 实例...")
    if dealer is None:
        print("✗ Dealer 为 None，尝试手动创建...")
        try:
            from api.settings import DOC_ENGINE
            if DOC_ENGINE == "elasticsearch":
                from rag.utils.es_conn import ESConnection
                doc_store = ESConnection()
            else:
                from rag.utils.infinity_conn import InfinityConnection
                doc_store = InfinityConnection()
            dealer = Dealer(doc_store)
            print(f"✓ 手动创建 Dealer 成功")
        except Exception as e:
            print(f"✗ 手动创建 Dealer 失败: {e}")
            return
    else:
        print(f"✓ Dealer 实例获取成功")

    # ========== 3. 执行检索 ==========
    print("\n[3/3] 执行关键词检索...")
    try:
        result = dealer._keyword_retrieval(
            question=question,
            tenant_ids=tenant_id,
            kb_ids=kb_ids,
            top_k=top_k
        )

        # ========== 4. 打印结果 ==========
        print("\n" + "=" * 60)
        print(f"[结果] 找到 {result['total']} 个页面")
        print("=" * 60)

        for i, chunk in enumerate(result['chunks'], 1):
            print(f"\n[#{i}] 相似度: {chunk['similarity']:.4f}")
            print(f"  页面ID: {chunk['page_id']}")
            print(f"  文档: {chunk['docnm_kwd']} (page {chunk.get('page_num_int', 'N/A')})")
            print(f"  知识库: {chunk['kb_id']}")
            if chunk.get('img_url'):
                print(f"  图片: {chunk['img_url'][:80]}...")
            if chunk.get('content_with_weight'):
                content = chunk['content_with_weight'][:100]
                print(f"  内容: {content}...")

    except Exception as e:
        print(f"\n✗ 检索失败: {e}")
        import traceback
        traceback.print_exc()


def test_parallel_retrieval():
    """测试三路并行检索"""

    # ========== 配置参数 ==========
    question = "what is the multi-stage training pipeline of Qwen3-VL-Embedding and Qwen3-VL-Reranker?"
    tenant_id = ["f98d14dcfd1511f09ad2420839d2c59b"]
    kb_ids = ["7205ff20dcff4fbea0475a4bedaea397"]
    image_topk = 10
    text_topk = 10
    keyword_topk = 10

    print("=" * 60)
    print(f"[测试] 三路并行检索")
    print(f"问题: {question}")
    print(f"租户ID: {tenant_id}")
    print(f"知识库IDs: {kb_ids}")
    print(f"图片Top-K: {image_topk}, 文本Top-K: {text_topk}, 关键词Top-K: {keyword_topk}")
    print("=" * 60)

    # ========== 初始化 ==========
    print("\n初始化...")
    init_settings()
    from api.settings import retrievaler
    from api.db.services.llm_service import LLMBundle

    dealer = retrievaler
    if dealer is None:
        from api.settings import DOC_ENGINE
        if DOC_ENGINE == "elasticsearch":
            from rag.utils.es_conn import ESConnection
            doc_store = ESConnection()
        else:
            from rag.utils.infinity_conn import InfinityConnection
            doc_store = InfinityConnection()
        dealer = Dealer(doc_store)

    # 获取 embedding 模型
    tenant_id_str = tenant_id[0] if isinstance(tenant_id, list) else tenant_id
    embd_mdl = LLMBundle(tenant_id_str, "embedding", "qwen3-vl")

    # ========== 执行三路检索 ==========
    print("\n执行三路并行检索...")
    try:
        results = dealer._parallel_retrieval(
            question=question,
            embd_mdl=embd_mdl,
            tenant_ids=tenant_id,
            kb_ids=kb_ids,
            image_topk=image_topk,
            text_topk=text_topk,
            keyword_topk=keyword_topk,
            similarity_threshold=0.1
        )

        # ========== 打印结果 ==========
        print("\n" + "=" * 60)
        print(f"[三路召回结果]")
        print("=" * 60)

        for retrieval_type, result in results.items():
            print(f"\n[{retrieval_type.upper()}] 找到 {result['total']} 个页面")
            for i, chunk in enumerate(result['chunks'][:3], 1):  # 只显示前3个
                print(f"  #{i} 相似度: {chunk['similarity']:.4f} | {chunk['docnm_kwd']} (page {chunk.get('page_num_int', 'N/A')})")

    except Exception as e:
        print(f"\n✗ 检索失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 测试单路关键词检索
    test_keyword_retrieval()

    # 测试三路并行检索
    # test_parallel_retrieval()
