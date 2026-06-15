# Agent MCP 新增检索工具设计

## 背景

当前 Agent 路径有 3 个 MCP 工具（`hybrid_retrieve`、`web_search`、`get_adjacent_pages`），存在以下盲区：
- LLM 不知道知识库中有哪些文档，无法做全局判断
- 检索只返回 300 字片段，看不到完整页面内容
- `document_generation` 表中的思维导图/知识点数据完全未被 Agent 利用

## 新增 3 个 Tool

### Tool 4: `list_documents`
- **数据源**: ES `ragflow_{tenant_id}` 索引
- **实现**: 使用 ES Terms Aggregation 对 `doc_id` + `docnm_kwd` 聚合，统计每文档页数范围
- **返回**: `{"total": N, "documents": [{"doc_id", "doc_name", "page_count", "first_page", "last_page"}]}`

### Tool 5: `get_full_page`
- **数据源**: ES `ragflow_{tenant_id}` 索引
- **实现**: ES 精确查询 `doc_id` + `page_num_int`，返回完整 `content_with_weight`
- **返回**: `{"page_id", "doc_id", "docnm_kwd", "page_num_int", "full_content", "img_url"}`
- **与 hybrid_retrieve 的区别**: 不做截断，返回页面完整 OCR 文本

### Tool 6: `get_knowledge_structure`
- **数据源**: MySQL `document_generation` 表 (Peewee ORM)
- **实现**: 查询 `generation_type = 'mindmap'` 的记录
- **返回**: `{"doc_id", "mindmap": {...}, "flashcards_count": N, "quiz_count": N}`
- **作用**: 让 LLM 了解课件的知识框架，用于回答结构性问题

## 改动范围

| 文件 | 改动 |
|------|------|
| `rag/agent/server/tools.py` | 新增 3 个 `_tool_*` 方法 |
| `rag/agent/server/server.py` | 注册 3 个新 MCP tool |
| `rag/agent/client/loop.py` | 更新 ReAct system prompt，加入新工具描述 |

## 不在此次范围

- `get_student_context`（需要 user_id 传递链路）
- `get_flashcards` / `get_quiz`（后续按需添加）
- `structured_search`（需要解析阶段加 content_type 字段）
