"""
测试 MCP Server 的 6 个工具。直接 python test_mcp_tools.py 运行。
在 main() 中注释/取消注释即可切换测试的工具。
"""

import json
import os
import sys
import time

_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
os.environ.setdefault("LIGHTEN", "1")

TENANT_IDS = ["85fde2168cdc4865a4d571d7e42b8a57"]
KB_IDS = ["c7ca723c7c804b86957ed0eb741e90f8"]
DOC_ID = "e142f52e6c804935a3ea96ed6e4a0459"
PAGE_NUM = 2

# 对应 dialog: 60db0c89cefa4d66a48f13e8e0e841f7 (知识表示方法)
DIALOG_TENANT_ID = "85fde2168cdc4865a4d571d7e42b8a57"
EMBD_ID = "qwen3-vl"           # 来自 kb: c7ca723c7c804b86957ed0eb741e90f8
RERANK_ID = "qwen3-vl-rerank"  # 来自 dialog.rerank_id

_executor = None


def init():
    global _executor
    if _executor:
        return _executor
    print("⏳ 初始化...", end=" ", flush=True)
    t0 = time.time()
    from rag.nlp.search import Dealer
    from rag.utils.es_conn import ESConnection
    from rag.agent.server.tools import MCPToolExecutor
    from api.db.services.llm_service import LLMBundle
    from api.db import LLMType

    doc_store = ESConnection()
    dealer = Dealer(doc_store)

    embd_mdl = rerank_mdl = chat_mdl = None
    try:
        embd_mdl = LLMBundle(DIALOG_TENANT_ID, LLMType.EMBEDDING, EMBD_ID)
        print(f"[embd: OK]", end=" ")
    except Exception as e:
        print(f"[embd: {e}]", end=" ")
    try:
        rerank_mdl = LLMBundle(DIALOG_TENANT_ID, LLMType.RERANK, RERANK_ID)
        print(f"[rerank: OK]", end=" ")
    except Exception as e:
        print(f"[rerank: {e}]", end=" ")
    try:
        chat_mdl = LLMBundle(DIALOG_TENANT_ID, LLMType.CHAT)
    except Exception:
        pass

    _executor = MCPToolExecutor(dealer=dealer, embd_mdl=embd_mdl, rerank_mdl=rerank_mdl, chat_mdl=chat_mdl)
    print(f"✅ ({time.time() - t0:.2f}s)")
    return _executor


def doprint(data, cut=300):
    if isinstance(data, str) and len(data) > cut:
        return data[:cut] + f"...({len(data)} chars)"
    if isinstance(data, list):
        return [doprint(v, cut) for v in data]
    if isinstance(data, dict):
        return {k: doprint(v, cut) for k, v in data.items()}
    return data


def run(name, fn, *a, **kw):
    print(f"\n{'='*60}")
    print(f"🔧 {name}")
    print(f"{'='*60}")
    t0 = time.time()
    try:
        r = fn(*a, **kw)
        print(json.dumps(doprint(r), ensure_ascii=False, indent=2))
        print(f"\n⏱ {time.time() - t0:.3f}s")
    except Exception as e:
        print(f"❌ ({time.time() - t0:.3f}s): {e}")
        import traceback; traceback.print_exc()


# ── 1. 列出知识库文档 ────────────────────────────────

def test_list_documents():
    exe = init()
    run("list_documents", exe._tool_list_documents, kb_ids=KB_IDS)


# ── 2. 混合检索 ─────────────────────────────────────

def test_hybrid_retrieve():
    exe = init()
    run("hybrid_retrieve", exe._tool_hybrid_retrieve,
        "传教士野人问题如何解决？", rerank_topk=3, tenant_ids=TENANT_IDS, kb_ids=KB_IDS,
    )


# ── 3. 获取页面完整内容 ──────────────────────────────

def test_get_full_page():
    exe = init()
    run("get_full_page", exe._tool_get_full_page, DOC_ID, PAGE_NUM, tenant_ids=TENANT_IDS, kb_ids=KB_IDS)


# ── 4. 获取相邻页面 ─────────────────────────────────

def test_get_adjacent_pages():
    exe = init()
    run("get_adjacent_pages", exe._tool_get_adjacent_pages,
        DOC_ID, PAGE_NUM, "both", 1, tenant_ids=TENANT_IDS, kb_ids=KB_IDS)


# ── 5. 获取知识结构 ─────────────────────────────────

def test_get_knowledge_structure():
    exe = init()
    run("get_knowledge_structure", exe._tool_get_knowledge_structure, DOC_ID)


# ── 6. 联网搜索 ─────────────────────────────────────

def test_web_search():
    exe = init()
    run("web_search", exe._tool_web_search,
        "人工智能教育最新进展",
        max_results=5,
    )


# ── main ────────────────────────────────────────────

def main():
    # ── 运行全部 6 个工具测试 ──

    test_list_documents()
    test_hybrid_retrieve()
    test_get_full_page()
    test_get_adjacent_pages()
    test_get_knowledge_structure()
    test_web_search()


if __name__ == "__main__":
    main()
