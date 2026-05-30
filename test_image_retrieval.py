#!/usr/bin/env python3
"""
测试 _vector_retrieval_by_image 函数

运行前确保：
1. 服务已启动（ES/Infinity + Redis + MySQL）
2. 有已索引的知识库数据
3. 配置好 embedding 模型
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from rag.utils.es_conn import ESConnection
from rag.nlp.search import Dealer
from api.db.services.llm_service import LLMBundle
from api.db import StatusEnum
from api.settings import init_settings


def test_vector_retrieval_by_image():
    """测试图片向量检索"""

    # ========== 配置参数 ==========
    question = "what is the multi-stage training pipeline of Qwen3-VL-Embedding and Qwen3-VL-Reranker?"  # 你的查询问题
    tenant_id = ["f98d14dcfd1511f09ad2420839d2c59b"]       # 租户ID（从数据库查看）
    kb_ids = ["01e9cbfe65e34b088df195a2486b0caa"]        # 知识库ID列表（从数据库查看）
    top_k = 50                  # 返回结果数

    print("=" * 60)
    print(f"[测试] 图片向量检索")
    print(f"问题: {question}")
    print(f"租户ID: {tenant_id}")
    print(f"知识库IDs: {kb_ids}")
    print(f"Top-K: {top_k}")
    print("=" * 60)

    # ========== 1. 初始化 Settings ==========
    print("\n[1/4] 初始化 Settings...")
    try:
        init_settings()
        from api.settings import retrievaler
        dealer = retrievaler
        print(f"✓ Settings 初始化成功")
    except Exception as e:
        print(f"✗ Settings 初始化失败: {e}")
        return

    # ========== 2. 获取 Dealer 实例 ==========
    print("\n[2/4] 获取 Dealer 实例...")
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

    # ========== 3. 获取 Embedding 模型 ==========
    print("\n[3/4] 加载 Embedding 模型...")
    try:
        embd_mdl = LLMBundle("f98d14dcfd1511f09ad2420839d2c59b", "embedding", "qwen3-vl")
        print(f"✓ Embedding 模型加载成功")
    except Exception as e:
        print(f"✗ Embedding 模型加载失败: {e}")
        print("  请检查 conf/service_conf.yaml 中的 embedding_model 配置")
        return

    # ========== 4. 执行检索 ==========
    print("\n[4/4] 执行图片向量检索...")
    try:
        result = dealer._vector_retrieval_by_text(
            question=question,
            embd_mdl=embd_mdl,
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


def test_with_custom_params():
    """使用自定义参数测试"""

    # 手动创建 Dealer（如果全局实例不可用）
    from rag.utils.es_conn import ESConnection

    print("手动创建连接...")
    doc_store = ESConnection()
    dealer = Dealer(doc_store)

    # 其余步骤同上
    # ...


if __name__ == "__main__":
    # 方式1: 使用默认全局实例
    test_vector_retrieval_by_image()

    # 方式2: 手动创建连接
    # test_with_custom_params()
