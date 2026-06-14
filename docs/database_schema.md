# RAGFlow-Plus 数据库表结构

> 数据库: `rag_flow` | 主机: `localhost:5455` | 用户: `root` | 表数量: 27

---

## 表分类概览

| 模块 | 表 | 说明 |
|------|-----|------|
| 对话 | `dialog` | AI 助教配置（提示词、模型、知识库绑定） |
| 对话 | `conversation` | 前台 Web 对话会话 |
| 对话 | `api_4_conversation` | 对外 API 对话记录（含 token、时长、反馈） |
| 对话 | `api_token` | 对外 API 访问令牌 |
| 知识库 | `knowledgebase` | 知识库配置 |
| 知识库 | `document` | 知识库文档（解析状态、分块数等） |
| 知识库 | `file` | 文件管理器文件 |
| 知识库 | `file2document` | 文件-文档关联 |
| 知识库 | `file_page` | 文件页面的 MinIO 存储信息 |
| 知识库 | `task` | 文档解析/索引任务队列 |
| 教育学习 | `document_generation` | 文档生成的课件内容（测验、思维导图、闪卡） |
| 教育学习 | `student_quiz_result` | 学生测验答题记录 |
| 教育学习 | `knowledge_point_mastery` | 知识点掌握度（间隔重复追踪） |
| 教育学习 | `student_card_progress` | 闪卡学习进度 |
| 教育学习 | `student_note` | 学生在文档上的笔记 |
| 班级 | `class` | 班级 |
| 班级 | `class_dialog` | 班级-助教关联 |
| 班级 | `user_class` | 用户-班级关联（含角色） |
| 用户 | `user` | 用户（is_superuser=1 表示教师） |
| 用户 | `tenant` | 租户（学校/机构） |
| 用户 | `user_tenant` | 用户-租户关联 |
| 用户 | `invitation_code` | 邀请码 |
| LLM | `llm` | LLM 模型定义 |
| LLM | `llm_factories` | LLM 厂商 |
| LLM | `tenant_llm` | 租户 LLM 配置（API Key 等） |
| 画布 | `canvas_template` | Agent 画布模板 |
| 画布 | `user_canvas` | 用户 Agent 画布 |

---

## `api_4_conversation`

对外 API 对话记录。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| dialog_id | varchar(32) | NO | MUL | NULL | 助教 ID |
| user_id | varchar(255) | NO | MUL | NULL | 用户 ID |
| message | longtext | YES |  | NULL | 对话消息 JSON |
| reference | longtext | YES |  | NULL | 检索引用 |
| tokens | int | NO |  | NULL | Token 消耗 |
| source | varchar(16) | YES | MUL | NULL | 来源 |
| dsl | longtext | YES |  | NULL | 画布 DSL |
| duration | float | NO | MUL | NULL | 对话耗时(秒) |
| round | int | NO | MUL | NULL | 对话轮次 |
| thumb_up | int | NO | MUL | NULL | 点赞 |

## `api_token`

对外 API 访问令牌。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| tenant_id | varchar(32) | NO | PRI | NULL |  |
| token | varchar(255) | NO | PRI | NULL |  |
| dialog_id | varchar(32) | YES | MUL | NULL |  |
| source | varchar(16) | YES | MUL | NULL |  |
| beta | varchar(255) | YES | MUL | NULL |  |

## `canvas_template`

Agent 画布模板。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| avatar | text | YES |  | NULL |  |
| title | varchar(255) | YES |  | NULL |  |
| description | text | YES |  | NULL |  |
| canvas_type | varchar(32) | YES | MUL | NULL |  |
| dsl | longtext | YES |  | NULL | 画布定义 DSL |

## `class`

班级。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| tenant_id | varchar(32) | NO | MUL | NULL | 租户 ID |
| name | varchar(100) | NO | MUL | NULL | 班级名称 |
| description | text | YES |  | NULL |  |
| status | varchar(1) | YES | MUL | NULL | 状态(1=有效) |

## `class_dialog`

班级-助教关联（N:M）。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| class_id | varchar(32) | NO | MUL | NULL | 班级 ID |
| dialog_id | varchar(32) | NO | MUL | NULL | 助教 ID |

## `conversation`

前台 Web 对话会话。每个会话包含完整 message JSON。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| dialog_id | varchar(32) | NO | MUL | NULL | 助教 ID |
| name | varchar(255) | YES | MUL | NULL | 会话名称 |
| message | longtext | YES |  | NULL | 对话消息 JSON 数组 |
| reference | longtext | YES |  | NULL | 检索引用 |
| user_id | varchar(255) | YES | MUL | NULL | 用户 ID |

## `dialog`

AI 助教配置（原 Chat App / Dialog）。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| tenant_id | varchar(32) | NO | MUL | NULL | 租户 ID |
| name | varchar(255) | YES | MUL | NULL | 助教名称 |
| description | text | YES |  | NULL | 助教描述 |
| icon | text | YES |  | NULL | 图标 URL |
| language | varchar(32) | YES | MUL | NULL | 语言 |
| llm_id | varchar(128) | NO |  | NULL | LLM 模型 |
| llm_setting | longtext | NO |  | NULL | LLM 参数 JSON |
| prompt_type | varchar(16) | NO | MUL | NULL | 提示词类型 |
| prompt_config | longtext | NO |  | NULL | 提示词配置 JSON |
| similarity_threshold | float | NO |  | NULL | 相似度阈值 |
| vector_similarity_weight | float | NO |  | NULL | 向量相似度权重 |
| top_n | int | NO |  | NULL | 召回数 |
| top_k | int | NO |  | NULL | 最终保留数 |
| do_refer | varchar(1) | NO |  | NULL | 是否引用 |
| rerank_id | varchar(128) | NO |  | NULL | 重排序模型 |
| kb_ids | longtext | NO |  | NULL | 关联知识库 ID 列表(逗号分隔) |
| status | varchar(1) | YES | MUL | NULL | 状态(1=有效) |

## `document`

知识库文档。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| thumbnail | text | YES |  | NULL | 缩略图 |
| kb_id | varchar(256) | NO | MUL | NULL | 知识库 ID |
| parser_id | varchar(32) | NO | MUL | NULL | 解析器类型 |
| parser_config | longtext | NO |  | NULL | 解析配置 |
| source_type | varchar(128) | NO | MUL | NULL | 来源类型 |
| type | varchar(32) | NO | MUL | NULL | 文档类型 |
| created_by | varchar(32) | NO | MUL | NULL | 创建者 |
| name | varchar(255) | YES | MUL | NULL | 文档名 |
| location | varchar(255) | YES | MUL | NULL | 文件位置 |
| size | int | NO | MUL | NULL | 文件大小 |
| token_num | int | NO | MUL | NULL | Token 数 |
| chunk_num | int | NO | MUL | NULL | 分块数 |
| progress | float | NO | MUL | NULL | 解析进度(0-1) |
| progress_msg | text | YES |  | NULL | 进度消息 |
| process_begin_at | datetime | YES | MUL | NULL | 处理开始时间 |
| process_duation | float | NO |  | NULL | 处理耗时 |
| meta_fields | longtext | YES |  | NULL | 元数据字段 |
| run | varchar(1) | YES | MUL | NULL | 运行状态 |
| status | varchar(1) | YES | MUL | NULL | 状态(1=有效) |

## `document_generation`

文档生成的课件内容。用于存储 LLM 为文档生成的测验(quiz)、思维导图(mindmap)、闪卡(flashcards)。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| doc_id | varchar(32) | NO | MUL | NULL | 文档 ID |
| generation_type | varchar(32) | NO | MUL | NULL | 类型: quiz / mindmap / flashcards |
| content | longtext | NO |  | NULL | 生成内容的 JSON |
| page_count | int | NO |  | NULL | 课件页数 |

## `file`

文件管理器文件。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| parent_id | varchar(32) | NO | MUL | NULL | 父文件夹 ID |
| tenant_id | varchar(32) | NO | MUL | NULL | 租户 ID |
| created_by | varchar(32) | NO | MUL | NULL | 创建者 |
| name | varchar(255) | NO | MUL | NULL | 文件名 |
| location | varchar(255) | YES | MUL | NULL | MinIO 位置 |
| size | int | NO | MUL | NULL | 文件大小 |
| type | varchar(32) | NO | MUL | NULL | 类型(file/folder) |
| source_type | varchar(128) | NO | MUL | NULL | 来源类型 |

## `file2document`

文件-文档关联（1:1）。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| file_id | varchar(32) | YES | MUL | NULL | 文件 ID |
| document_id | varchar(32) | YES | MUL | NULL | 文档 ID |

## `file_page`

文件页面的 MinIO 存储信息。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| file_id | varchar(32) | NO | MUL | NULL |  |
| page_number | int | NO | MUL | NULL | 页码 |
| location | varchar(255) | NO |  | NULL | MinIO 位置 |
| size | int | NO |  | NULL | 文件大小 |
| width | int | NO |  | NULL | 页面宽度 |
| height | int | NO |  | NULL | 页面高度 |
| format | varchar(16) | NO |  | NULL | 格式 |

## `invitation_code`

邀请码。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| code | varchar(32) | NO | MUL | NULL | 邀请码 |
| visit_time | datetime | YES | MUL | NULL | 访问时间 |
| user_id | varchar(32) | YES | MUL | NULL |  |
| tenant_id | varchar(32) | YES | MUL | NULL |  |
| status | varchar(1) | YES | MUL | NULL | 状态 |

## `knowledge_point_mastery`

知识点掌握度追踪（基于间隔重复算法 SM-2）。

学生每做一次测验（`student_quiz_result`），系统按知识点（`node_id`）更新该表，追踪每个知识点的正确/错误次数，并计算下一次复习时间。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| student_id | varchar(32) | NO | MUL | NULL | 学生 ID |
| doc_id | varchar(32) | NO | MUL | NULL | 文档 ID |
| node_id | varchar(64) | NO |  | NULL | 知识点 ID（如 ch1_2） |
| correct_count | int | NO |  | NULL | 答对次数 |
| wrong_count | int | NO |  | NULL | 答错次数 |
| last_review_time | bigint | YES |  | NULL | 上次复习时间戳 |
| next_review_time | bigint | YES |  | NULL | 下次复习时间戳 |
| ease_factor | float | NO |  | NULL | SM-2 算法的 ease factor（≥1.3） |
| review_count | int | NO |  | NULL | 复习总次数 |

## `knowledgebase`

知识库配置。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| avatar | text | YES |  | NULL |  |
| tenant_id | varchar(32) | NO | MUL | NULL | 租户 ID |
| name | varchar(128) | NO | MUL | NULL | 知识库名称 |
| language | varchar(32) | YES | MUL | NULL | 语言 |
| description | text | YES |  | NULL |  |
| embd_id | varchar(128) | NO | MUL | NULL | 嵌入模型 |
| permission | varchar(16) | NO | MUL | NULL | 权限 |
| created_by | varchar(32) | NO | MUL | NULL | 创建者 |
| doc_num | int | NO | MUL | NULL | 文档数 |
| token_num | int | NO | MUL | NULL | Token 数 |
| chunk_num | int | NO | MUL | NULL | 分块数 |
| similarity_threshold | float | NO | MUL | NULL | 相似度阈值 |
| vector_similarity_weight | float | NO | MUL | NULL | 向量相似度权重 |
| parser_id | varchar(32) | NO | MUL | NULL | 解析器 |
| parser_config | longtext | NO |  | NULL | 解析配置 |
| pagerank | int | NO |  | NULL | PageRank 值 |
| status | varchar(1) | YES | MUL | NULL | 状态 |

## `llm`

LLM 模型定义。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| llm_name | varchar(128) | NO | PRI | NULL | 模型名称 |
| model_type | varchar(128) | NO | MUL | NULL | 模型类型(chat/embedding/rerank) |
| fid | varchar(128) | NO | PRI | NULL | 厂商 ID |
| max_tokens | int | NO |  | NULL | 最大 Token |
| tags | varchar(255) | NO | MUL | NULL | 标签 |
| status | varchar(1) | YES | MUL | NULL | 状态 |

## `llm_factories`

LLM 厂商定义。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| name | varchar(128) | NO | PRI | NULL | 厂商名称 |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| logo | text | YES |  | NULL | Logo URL |
| tags | varchar(255) | NO | MUL | NULL |  |
| status | varchar(1) | YES | MUL | NULL |  |

## `student_card_progress`

学生闪卡学习进度。记录每个文档中每张闪卡的学习状态。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| student_id | varchar(32) | NO | MUL | NULL | 学生 ID |
| doc_id | varchar(32) | NO | MUL | NULL | 文档 ID |
| card_index | int | NO |  | NULL | 闪卡序号 |
| status | varchar(16) | NO |  | NULL | 状态: remembered / forgotten / learning |

## `student_note`

学生在文档上的笔记。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| student_id | varchar(32) | NO | MUL | NULL | 学生 ID |
| doc_id | varchar(32) | NO | MUL | NULL | 文档 ID |
| page_number | int | NO |  | NULL | 页码 |
| content | longtext | YES |  | NULL | 笔记内容 |

## `student_quiz_result`

学生测验答题记录。记录每道题的作答情况，用于计算知识点掌握度。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| student_id | varchar(32) | NO | MUL | NULL | 学生 ID |
| doc_id | varchar(32) | NO | MUL | NULL | 文档 ID |
| question_index | int | NO |  | NULL | 题目序号 |
| student_answer | varchar(4) | YES |  | NULL | 学生答案(A/B/C/D) |
| is_correct | tinyint(1) | NO |  | NULL | 是否正确(0/1) |

## `task`

文档解析/索引任务队列。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| doc_id | varchar(32) | NO | MUL | NULL | 文档 ID |
| from_page | int | NO |  | NULL | 起始页 |
| to_page | int | NO |  | NULL | 结束页 |
| task_type | varchar(32) | NO |  | NULL | 任务类型 |
| begin_at | datetime | YES | MUL | NULL | 开始时间 |
| process_duation | float | NO |  | NULL | 处理耗时 |
| progress | float | NO | MUL | NULL | 进度 |
| progress_msg | text | YES |  | NULL | 进度消息 |
| retry_count | int | NO |  | NULL | 重试次数 |
| digest | text | YES |  | NULL | 摘要 |
| chunk_ids | longtext | YES |  | NULL | 分块 ID 列表 |

## `tenant`

租户（学校/机构）。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| name | varchar(100) | YES | MUL | NULL | 租户名称 |
| public_key | varchar(255) | YES | MUL | NULL | 公钥 |
| llm_id | varchar(128) | NO | MUL | NULL | 默认聊天模型 |
| embd_id | varchar(128) | NO | MUL | NULL | 默认嵌入模型 |
| asr_id | varchar(128) | NO | MUL | NULL | 默认 ASR 模型 |
| img2txt_id | varchar(128) | NO | MUL | NULL | 默认图转文模型 |
| rerank_id | varchar(128) | NO | MUL | NULL | 默认重排序模型 |
| tts_id | varchar(256) | YES | MUL | NULL | 默认 TTS 模型 |
| parser_ids | varchar(256) | NO | MUL | NULL | 解析器列表 |
| credit | int | NO | MUL | NULL | 配额 |
| status | varchar(1) | YES | MUL | NULL | 状态 |

## `tenant_llm`

租户 LLM 配置（API Key 等）。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| tenant_id | varchar(32) | NO | PRI | NULL | 租户 ID |
| llm_factory | varchar(128) | NO | PRI | NULL | LLM 厂商 |
| model_type | varchar(128) | YES | MUL | NULL | 模型类型 |
| llm_name | varchar(128) | NO | PRI | NULL | 模型名称 |
| api_key | varchar(1024) | YES | MUL | NULL | API Key |
| api_base | varchar(255) | YES |  | NULL | API 地址 |
| max_tokens | int | NO | MUL | NULL | 最大 Token |
| used_tokens | int | NO | MUL | NULL | 已用 Token |

## `user`

用户。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| access_token | varchar(255) | YES | MUL | NULL |  |
| nickname | varchar(100) | NO | MUL | NULL | 昵称 |
| password | varchar(255) | YES | MUL | NULL | 密码 |
| email | varchar(255) | NO | MUL | NULL | 邮箱 |
| avatar | text | YES |  | NULL | 头像 URL |
| language | varchar(32) | YES | MUL | NULL | 语言 |
| color_schema | varchar(32) | YES | MUL | NULL | 颜色主题 |
| timezone | varchar(64) | YES | MUL | NULL | 时区 |
| last_login_time | datetime | YES | MUL | NULL | 最后登录 |
| is_authenticated | varchar(1) | NO | MUL | NULL | 是否认证 |
| is_active | varchar(1) | NO | MUL | NULL | 是否激活 |
| is_anonymous | varchar(1) | NO | MUL | NULL | 是否匿名 |
| login_channel | varchar(255) | YES | MUL | NULL | 登录渠道 |
| status | varchar(1) | YES | MUL | NULL | 状态 |
| is_superuser | tinyint(1) | YES | MUL | NULL | 是否超级用户(1=教师) |
| is_system | tinyint(1) | YES | MUL | NULL | 是否系统管理员 |

## `user_canvas`

用户 Agent 画布。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| avatar | text | YES |  | NULL |  |
| user_id | varchar(255) | NO | MUL | NULL |  |
| title | varchar(255) | YES |  | NULL |  |
| description | text | YES |  | NULL |  |
| canvas_type | varchar(32) | YES | MUL | NULL |  |
| dsl | longtext | YES |  | NULL | 画布定义 DSL |

## `user_class`

用户-班级关联（N:M，含角色）。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| user_id | varchar(32) | NO | MUL | NULL | 用户 ID |
| class_id | varchar(32) | NO | MUL | NULL | 班级 ID |
| role | varchar(32) | NO | MUL | NULL | 角色: teacher / student |
| status | varchar(1) | YES | MUL | NULL | 状态 |

## `user_tenant`

用户-租户关联。

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| user_id | varchar(32) | NO | MUL | NULL |  |
| tenant_id | varchar(32) | NO | MUL | NULL |  |
| role | varchar(32) | NO | MUL | NULL | 角色 |
| invited_by | varchar(32) | NO | MUL | NULL | 邀请人 |
| status | varchar(1) | YES | MUL | NULL | 状态 |

---

## 关键业务关系

### 班级 → 助教 → 知识库

```
class ──< class_dialog >── dialog ──> kb_ids ──> knowledgebase
  │
  └──< user_class >── user
```

### 学习数据流

```
student_quiz_result ──> knowledge_point_mastery (间隔重复)
                     ──> document_generation (生成内容关联 doc)
student_card_progress ──> document (闪卡进度)
student_note ──> document (笔记)
conversation ──> dialog (对话记录)
```

### 学习统计 API 数据来源

`/v1/learning_stats/*` 接口从以下表聚合数据：

| 统计项 | 来源表 |
|--------|--------|
| 会话数 | `conversation` (按 dialog_id + user_id 计数) |
| 提问数 | `conversation.message` JSON (role='user' 条目数) |
| 测验数 | `student_quiz_result` (按 doc_id 计数) |
| 题目掌握度 | `student_quiz_result` + `document_generation` (正确题数/总题数) |
| 文档覆盖率 | `student_quiz_result` (distinct doc_id / 总文档数) |
| 连续学习天数 | `conversation` (按 create_date 计算连续天数) |
| 今日会话数 | `conversation` (当天 create_date 计数) |
