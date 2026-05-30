#!/usr/bin/env python3
"""
测试 _parallel_retrieval 函数（三路并行召回）

运行前确保：
1. 服务已启动（ES/Infinity + Redis + MySQL）
2. 有已索引的知识库数据（包含图片和文本向量）
3. 配置好 embedding 模型
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from rag.nlp.search import Dealer
from api.settings import init_settings
from api.db.services.llm_service import LLMBundle


def test_parallel_retrieval():
    """测试三路并行召回"""

    # ========== 配置参数 ==========
    question = "what is the multi-stage training pipeline of Qwen3-VL-Embedding and Qwen3-VL-Reranker?"
    tenant_id = ["f98d14dcfd1511f09ad2420839d2c59b"]
    kb_ids = ["01e9cbfe65e34b088df195a2486b0caa"]
    image_topk = 10
    text_topk = 10
    keyword_topk = 10

    print("=" * 60)
    print(f"[测试] 三路并行召回")
    print(f"问题: {question}")
    print(f"租户ID: {tenant_id}")
    print(f"知识库IDs: {kb_ids}")
    print(f"图片Top-K: {image_topk}, 文本Top-K: {text_topk}, 关键词Top-K: {keyword_topk}")
    print("=" * 60)

    # ========== 1. 初始化 Settings ==========
    print("\n[1/3] 初始化 Settings...")
    try:
        init_settings()
        from api.settings import retrievaler
        dealer = retrievaler
        print(f"✓ Settings 初始化成功")
    except Exception as e:
        print(f"✗ Settings 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # ========== 2. 获取 Dealer 和 Embedding 模型 ==========
    print("\n[2/3] 获取 Dealer 和 Embedding 模型...")

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

    # 获取 embedding 模型
    try:
        tenant_id_str = tenant_id[0] if isinstance(tenant_id, list) else tenant_id
        embd_mdl = LLMBundle(tenant_id_str, "embedding", "qwen3-vl")
        print(f"✓ Embedding 模型加载成功")
    except Exception as e:
        print(f"✗ Embedding 模型加载失败: {e}")
        return

    # ========== 3. 执行三路并行检索 ==========
    print("\n[3/3] 执行三路并行检索...")
    try:
        results = dealer._parallel_retrieval(
            question=question,
            embd_mdl=embd_mdl,
            tenant_ids=tenant_id,
            kb_ids=kb_ids,
            image_topk=image_topk,
            text_topk=text_topk,
            keyword_topk=keyword_topk,
        )

        # ========== 4. 打印结果 ==========
        print("\n" + "=" * 60)
        print(f"[三路召回结果汇总]")
        print("=" * 60)

        for retrieval_type in ["image", "text", "keyword"]:
            result = results.get(retrieval_type, {"total": 0, "chunks": []})
            print(f"\n[{retrieval_type.upper()}] 召回 {result['total']} 个页面")

            # 显示前 3 个结果
            for i, chunk in enumerate(result['chunks'][:3], 1):
                print(f"  #{i} 相似度: {chunk['similarity']:.4f} | {chunk['docnm_kwd']} (page {chunk.get('page_num_int', 'N/A')})")

            if result['total'] > 3:
                print(f"  ... 还有 {result['total'] - 3} 个结果")

        # ========== 5. 分析重叠情况 ==========
        print("\n" + "=" * 60)
        print(f"[结果重叠分析]")
        print("=" * 60)

        image_ids = set(c['page_id'] for c in results.get('image', {}).get('chunks', []))
        text_ids = set(c['page_id'] for c in results.get('text', {}).get('chunks', []))
        keyword_ids = set(c['page_id'] for c in results.get('keyword', {}).get('chunks', []))

        print(f"图片召回: {len(image_ids)} 个")
        print(f"文本召回: {len(text_ids)} 个")
        print(f"关键词召回: {len(keyword_ids)} 个")

        # 计算重叠
        image_text = image_ids & text_ids
        image_keyword = image_ids & keyword_ids
        text_keyword = text_ids & keyword_ids
        all_three = image_ids & text_ids & keyword_ids

        print(f"\n图片∩文本: {len(image_text)} 个")
        print(f"图片∩关键词: {len(image_keyword)} 个")
        print(f"文本∩关键词: {len(text_keyword)} 个")
        print(f"三路重叠: {len(all_three)} 个")

        # 计算总召回（去重）
        total_unique = len(image_ids | text_ids | keyword_ids)
        print(f"\n总召回（去重）: {total_unique} 个页面")

    except Exception as e:
        print(f"\n✗ 检索失败: {e}")
        import traceback
        traceback.print_exc()


def test_parallel_with_different_params():
    """测试不同参数配置下的三路召回"""

    # 测试不同的 top_k 配置
    configs = [
        {"image_topk": 5, "text_topk": 5, "keyword_topk": 10, "name": "均衡配置"},
        {"image_topk": 20, "text_topk": 5, "keyword_topk": 5, "name": "图片优先"},
        {"image_topk": 5, "text_topk": 20, "keyword_topk": 5, "name": "文本优先"},
    ]

    question = "what is the multi-stage training pipeline of Qwen3-VL-Embedding and Qwen3-VL-Reranker?"
    tenant_id = ["f98d14dcfd1511f09ad2420839d2c59b"]
    kb_ids = ["01e9cbfe65e34b088df195a2486b0caa"]

    # 初始化（只执行一次）
    print("初始化...")
    init_settings()
    from api.settings import retrievaler
    from api.settings import DOC_ENGINE

    dealer = retrievaler
    if dealer is None:
        if DOC_ENGINE == "elasticsearch":
            from rag.utils.es_conn import ESConnection
            dealer = Dealer(ESConnection())
        else:
            from rag.utils.infinity_conn import InfinityConnection
            dealer = Dealer(InfinityConnection())

    tenant_id_str = tenant_id[0] if isinstance(tenant_id, list) else tenant_id
    embd_mdl = LLMBundle(tenant_id_str, "embedding", "qwen3-vl")

    # 测试不同配置
    for config in configs:
        name = config.pop("name")
        print(f"\n{'='*60}")
        print(f"测试配置: {name}")
        print(f"{'='*60}")

        try:
            results = dealer._parallel_retrieval(
                question=question,
                embd_mdl=embd_mdl,
                tenant_ids=tenant_id,
                kb_ids=kb_ids,
                **config
            )

            total = sum(r.get('total', 0) for r in results.values())
            print(f"总召回: {total} 个页面")
            for retrieval_type, result in results.items():
                print(f"  {retrieval_type}: {result.get('total', 0)} 个")

        except Exception as e:
            print(f"✗ 配置 '{name}' 失败: {e}")


if __name__ == "__main__":
    # 测试三路并行检索
    test_parallel_retrieval()

    # 测试不同参数配置
    # test_parallel_with_different_params()
