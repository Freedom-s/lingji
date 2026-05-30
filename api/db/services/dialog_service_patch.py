"""
Dialog Service 混合检索集成补丁

这个文件提供了在 dialog_service.py 中集成混合检索的代码参考
"""

def integrate_hybrid_retrieval():
    """
    在 dialog_service.py 的 chat 函数中添加混合检索支持

    找到这段代码（大约在第 207-230 行）：

    ```python
    # 检索模式选择
    use_page_vector_retrieval = "page_vector"  # 临时设置为使用页面向量检索

    if use_page_vector_retrieval == "page_vector":
        # 单纯只使用图片向量进行检索
        kbinfos = retriever.page_vector_retrieval(...)
    ```

    替换为：

    ```python
    # 检索模式选择
    use_hybrid_retrieval = kwargs.get("use_hybrid_retrieval", False)

    if use_hybrid_retrieval:
        # 使用三路并行检索
        kbinfos = retriever.hybrid_page_retrieval(
            question=" ".join(questions),
            embd_mdl=embd_mdl,
            tenant_ids=tenant_ids,
            kb_ids=dialog.kb_ids,
            rerank_mdl=rerank_mdl,
            chat_mdl=chat_mdl,  # 用于前后页评估
            image_topk=kwargs.get("image_topk", 6),
            text_topk=kwargs.get("text_topk", 6),
            keyword_topk=kwargs.get("keyword_topk", 6),
            rrf_k=kwargs.get("rrf_k", 60),
            rrf_topk=kwargs.get("rrf_topk", 4),
            rerank_final_topk=kwargs.get("rerank_final_topk", 2),
            similarity_threshold=dialog.similarity_threshold,
            enable_context_recall=kwargs.get("enable_context_recall", False),
            context_recall_max_pages=kwargs.get("context_recall_max_pages", 1)
        )
        use_page_vector_retrieval = "hybrid"  # 标记为混合检索模式
    else:
        use_page_vector_retrieval = "page_vector"  # 使用原有的单路检索

    if use_page_vector_retrieval == "page_vector":
        # 单纯只使用图片向量进行检索
        kbinfos = retriever.page_vector_retrieval(...)
    ```
    """

    pass


# 使用示例（在 conversation_app.py 的 completion 接口中）:
def example_usage_in_completion():
    """
    在 api/apps/conversation_app.py 的 completion 函数中添加参数支持

    找到第 284-346 行的 completion 函数，在 kwargs 参数中添加混合检索参数：

    ```python
    @manager.route("/completion", methods=["POST"])
    @login_required
    @validate_request("conversation_id", "messages")
    def completion():
        req = request.json
        msg = []

        # ... 现有的消息处理代码 ...

        try:
            # ... 现有的对话和知识库获取代码 ...

            # ===== 新增：混合检索参数 =====
            # 从请求中获取混合检索参数
            hybrid_params = req.get("hybrid_retrieval", {})
            if hybrid_params:
                req.update({
                    "use_hybrid_retrieval": True,
                    "image_topk": hybrid_params.get("image_topk", 6),
                    "text_topk": hybrid_params.get("text_topk", 6),
                    "keyword_topk": hybrid_params.get("keyword_topk", 6),
                    "rrf_k": hybrid_params.get("rrf_k", 60),
                    "rrf_topk": hybrid_params.get("rrf_topk", 4),
                    "rerank_final_topk": hybrid_params.get("rerank_final_topk", 2),
                    "enable_context_recall": hybrid_params.get("enable_context_recall", False),
                    "context_recall_max_pages": hybrid_params.get("context_recall_max_pages", 1),
                })

            # ... 继续原有的流程 ...
            for ans in chat(dia, msg, True, **req):
                # ...
        except Exception as e:
            # ...
    ```

    前端调用示例：

    ```javascript
    fetch('/api/conversation/completion', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            conversation_id: conversationId,
            messages: messages,
            hybrid_retrieval: {
                image_topk: 6,
                text_topk: 6,
                keyword_topk: 6,
                rrf_topk: 4,
                rerank_final_topk: 2,
                enable_context_recall: true
            }
        })
    })
    ```
    """

    pass
