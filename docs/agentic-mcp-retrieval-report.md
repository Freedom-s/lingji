# Agentic MCP 检索架构设计与实现

> 研究生组会汇报 — RAGFlow-Plus 高校 AI 助学平台

## 1. 工作目标

为 RAGFlow-Plus 构建 **Agentic MCP 检索架构**，让 LLM 能自主决定"查什么 → 结果够不够 → 是否需要再查 → 如何回答"，替代传统的固定流程检索。

## 2. 核心思路

```
传统 RAG:  用户提问 → 固定检索 → 拼接上下文 → LLM 回答（LLM 被动接收）
Agent RAG: 用户提问 → LLM 自主决策 → 调用工具 → 观察结果 → 循环 → 回答
```

用 **MCP 协议**（Model Context Protocol，Anthropic 开源）将检索能力封装为标准化工具，LLM 通过 **ReAct 循环**（Reasoning + Acting）自主调用。

## 3. 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│  Flask API Server (port 9380)                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  _stream_with_agent()                                │   │
│  │    → AgentLoop.run()   (ReAct 循环)                  │   │
│  │      → MCPClient       (SSE 协议通信)                │   │
│  │      → LLMBundle       (Qwen3-VL via SiliconFlow)     │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP SSE
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  MCP Server (port 9390, FastMCP)                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  6 个检索工具                                        │   │
│  │  ├── hybrid_retrieve       三路并行 + RRF + Rerank   │   │
│  │  ├── list_documents        列出知识库文档            │   │
│  │  ├── get_full_page         获取页面完整内容          │   │
│  │  ├── get_knowledge_structure  获取知识结构（思维导图）│   │
│  │  ├── get_adjacent_pages    获取相邻页面              │   │
│  │  └── web_search            Tavily 联网搜索           │   │
│  └──────────────────────────────────────────────────────┘   │
│                       ↓                                     │
│  MCPToolExecutor → ES (RAG 检索) + MySQL (课件数据)         │
└─────────────────────────────────────────────────────────────┘
```

## 4. 关键技术点

### 4.1 ReAct 自主决策循环

LLM 在每个 turn 看到：System Prompt + 对话历史 + 可用工具列表 + 已检索到的内容。它自主决定：

- **调用工具** → 拿到结果 → 追加到消息列表 → 继续下一轮
- **直接回答** → 退出循环 → 流式生成答案

安全阀：最多 8 轮 tool call，防止无限循环。

### 4.2 三路并行混合检索

```
hybrid_retrieve(query)
  ├── 图片向量检索 (image_{dim}_vec)     ┐
  ├── 文本向量检索 (text_{dim}_vec)      ┤ ThreadPoolExecutor
  └── 关键词 BM25 检索 (content_ltks)    ┘
        ↓
  RRF 融合 (Reciprocal Rank Fusion, k=60)
        ↓
  多模态重排序 (文本 + 图片 base64)
        ↓
  Top-K 结果 + 来源标注
```

### 4.3 MCP 协议解耦

- **工具发现**：`MCPClient.list_tools()` 动态获取所有工具，自动转换为 OpenAI function calling 格式
- **格式兜底**：`_format_tool_result` 三档处理 — summary 字段（工具自描述）→ 已知格式解析 → JSON 透传
- **新增工具**：只需在 MCP Server 注册 `@mcp.tool()`，客户端零改动

### 4.4 推理过程可视化

Agent 调用工具时 yield 带 `<tool_call>` XML 标签的事件，前端 `replaceToolCallToSection` 转为蓝色折叠卡片：

```
🔧 调用工具: list_documents
  ┌─────────────────────────────────────────┐
  │ [1] 第二章 知识表示方法.pptx (165页)    │
  │ [2] 大模型在教学中的应用.pptx (19页)    │
  │ [3] LightRAG框架下...pdf (7页)          │
  └─────────────────────────────────────────┘

🔧 调用工具: hybrid_retrieve
  ┌─────────────────────────────────────────┐
  │ [1] 第二章 知识表示方法.pptx p110 (0.05)│
  │ [2] 第二章 知识表示方法.pptx p151 (0.05)│
  └─────────────────────────────────────────┘
```

## 5. 实际效果

### 5.1 单轮检索

**提问：** "知识库中有哪些课件文档？"

Agent 自主调用 `list_documents` → 返回 3 个文档名 + 页数

### 5.2 多轮检索 + 跨文档对比

**提问：** "请帮我查找知识表示方法中关于语义网络的内容，并和大模型在教学中的应用中关于个性化辅导的内容做对比"

Agent 自主执行：
1. `list_documents` → 了解知识库结构
2. `get_knowledge_structure("413019ec...")` → 获取"知识表示方法"思维导图
3. `get_knowledge_structure("004d2375...")` → 获取"大模型在教学中的应用"思维导图
4. `hybrid_retrieve` → 检索语义网络内容
5. `hybrid_retrieve` → 检索个性化辅导内容
6. 生成四维对比分析表（核心机制 / 知识准确性 / 动态更新 / 个性化支持）

## 6. 核心代码改动

| 文件 | 说明 |
|------|------|
| `rag/agent/server/tools.py` | MCPToolExecutor：8 个内部检索方法 + 3 个新增工具 |
| `rag/agent/server/server.py` | FastMCP 服务：6 个 `@mcp.tool()` 注册 |
| `rag/agent/client/loop.py` | AgentLoop：ReAct 循环、工具格式化、MinIO URL 转换 |
| `rag/agent/client/mcp_client.py` | MCPClient：原生 aiohttp 实现 MCP SSE 协议 |
| `rag/agent/client/memory.py` | 三层记忆：Working / ShortTerm(Redis) / LongTerm(MySQL) |
| `api/apps/conversation_app.py` | `_stream_with_agent` 入口 + `AGENT_ENABLED` 开关 |
| `web/src/utils/chat.ts` | `replaceToolCallToSection`：工具调用可视化 |
| `web/src/pages/chat/markdown-content/index.tsx` | 处理管道集成 |
| `web/src/pages/chat/markdown-content/index.less` | 蓝色工具卡片样式 |
| `web/src/components/message-item/page-reference-item.tsx` | ChunkImage 替换裸 img |

## 7. 调试中解决的问题

| 问题 | 根因 | 修复 |
|------|------|------|
| MCP Client 连接失败 | FastMCP Client 需 `async with` 上下文 | 原生 aiohttp 实现 SSE 协议 |
| MCP 握手失败 | 缺少 `initialize` RPC | 添加协议初始化 + `initialized` 通知 |
| 工具调用返回空 | `dataStore.search` 参数位置偏移 | 修正为正确签名 |
| LLM 不调工具 | System Prompt 过长 | 简化为一行提示 |
| tool_call 内容被覆盖 | 流式回答 overwrite 工具标签 | 累积 `tool_call_log` 并 prepend |
| 引用图片不显示 | `minio://` URL 浏览器不认 | `_convert_minio_url` 转 HTTP |
| 相似度显示为 0% | 字段名 `score` vs `similarity` | 统一为 `similarity` + `content_with_weight` |
| 系统代理劫持 | Clash 代理 7890 端口 | `proxies=None` + `trust_env=False` |

## 8. 后续方向

- Planner 模块接入：LLM 意图分类（chat / retrieve / compare）→ 优化首轮决策
- Observer 模块接入：检索质量评估 → 自动调整策略
- `get_student_context` 工具：基于 `knowledge_point_mastery` 表实现个性化
- MCP Server 并发安全：全局 `_tool_executor` 改为请求级隔离
