# RAGFlow 数据库表结构

> 数据库: `rag_flow` | 主机: `localhost:5455` | 表数量: 22

---

## `api_4_conversation`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| dialog_id | varchar(32) | NO | MUL | NULL |  |
| user_id | varchar(255) | NO | MUL | NULL |  |
| message | longtext | YES |  | NULL |  |
| reference | longtext | YES |  | NULL |  |
| tokens | int | NO |  | NULL |  |
| source | varchar(16) | YES | MUL | NULL |  |
| dsl | longtext | YES |  | NULL |  |
| duration | float | NO | MUL | NULL |  |
| round | int | NO | MUL | NULL |  |
| thumb_up | int | NO | MUL | NULL |  |

## `api_token`

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
| dsl | longtext | YES |  | NULL |  |

## `class`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| tenant_id | varchar(32) | NO | MUL | NULL |  |
| name | varchar(100) | NO | MUL | NULL |  |
| description | text | YES |  | NULL |  |
| status | varchar(1) | YES | MUL | NULL |  |

## `class_dialog`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| class_id | varchar(32) | NO | MUL | NULL |  |
| dialog_id | varchar(32) | NO | MUL | NULL |  |

## `conversation`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| dialog_id | varchar(32) | NO | MUL | NULL |  |
| name | varchar(255) | YES | MUL | NULL |  |
| message | longtext | YES |  | NULL |  |
| reference | longtext | YES |  | NULL |  |
| user_id | varchar(255) | YES | MUL | NULL |  |

## `dialog`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| tenant_id | varchar(32) | NO | MUL | NULL |  |
| name | varchar(255) | YES | MUL | NULL |  |
| description | text | YES |  | NULL |  |
| icon | text | YES |  | NULL |  |
| language | varchar(32) | YES | MUL | NULL |  |
| llm_id | varchar(128) | NO |  | NULL |  |
| llm_setting | longtext | NO |  | NULL |  |
| prompt_type | varchar(16) | NO | MUL | NULL |  |
| prompt_config | longtext | NO |  | NULL |  |
| similarity_threshold | float | NO |  | NULL |  |
| vector_similarity_weight | float | NO |  | NULL |  |
| top_n | int | NO |  | NULL |  |
| top_k | int | NO |  | NULL |  |
| do_refer | varchar(1) | NO |  | NULL |  |
| rerank_id | varchar(128) | NO |  | NULL |  |
| kb_ids | longtext | NO |  | NULL |  |
| status | varchar(1) | YES | MUL | NULL |  |

## `document`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| thumbnail | text | YES |  | NULL |  |
| kb_id | varchar(256) | NO | MUL | NULL |  |
| parser_id | varchar(32) | NO | MUL | NULL |  |
| parser_config | longtext | NO |  | NULL |  |
| source_type | varchar(128) | NO | MUL | NULL |  |
| type | varchar(32) | NO | MUL | NULL |  |
| created_by | varchar(32) | NO | MUL | NULL |  |
| name | varchar(255) | YES | MUL | NULL |  |
| location | varchar(255) | YES | MUL | NULL |  |
| size | int | NO | MUL | NULL |  |
| token_num | int | NO | MUL | NULL |  |
| chunk_num | int | NO | MUL | NULL |  |
| progress | float | NO | MUL | NULL |  |
| progress_msg | text | YES |  | NULL |  |
| process_begin_at | datetime | YES | MUL | NULL |  |
| process_duation | float | NO |  | NULL |  |
| meta_fields | longtext | YES |  | NULL |  |
| run | varchar(1) | YES | MUL | NULL |  |
| status | varchar(1) | YES | MUL | NULL |  |

## `file`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| parent_id | varchar(32) | NO | MUL | NULL |  |
| tenant_id | varchar(32) | NO | MUL | NULL |  |
| created_by | varchar(32) | NO | MUL | NULL |  |
| name | varchar(255) | NO | MUL | NULL |  |
| location | varchar(255) | YES | MUL | NULL |  |
| size | int | NO | MUL | NULL |  |
| type | varchar(32) | NO | MUL | NULL |  |
| source_type | varchar(128) | NO | MUL | NULL |  |

## `file2document`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| file_id | varchar(32) | YES | MUL | NULL |  |
| document_id | varchar(32) | YES | MUL | NULL |  |

## `file_page`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| file_id | varchar(32) | NO | MUL | NULL |  |
| page_number | int | NO | MUL | NULL |  |
| location | varchar(255) | NO |  | NULL |  |
| size | int | NO |  | NULL |  |
| width | int | NO |  | NULL |  |
| height | int | NO |  | NULL |  |
| format | varchar(16) | NO |  | NULL |  |

## `invitation_code`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| code | varchar(32) | NO | MUL | NULL |  |
| visit_time | datetime | YES | MUL | NULL |  |
| user_id | varchar(32) | YES | MUL | NULL |  |
| tenant_id | varchar(32) | YES | MUL | NULL |  |
| status | varchar(1) | YES | MUL | NULL |  |

## `knowledgebase`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| avatar | text | YES |  | NULL |  |
| tenant_id | varchar(32) | NO | MUL | NULL |  |
| name | varchar(128) | NO | MUL | NULL |  |
| language | varchar(32) | YES | MUL | NULL |  |
| description | text | YES |  | NULL |  |
| embd_id | varchar(128) | NO | MUL | NULL |  |
| permission | varchar(16) | NO | MUL | NULL |  |
| created_by | varchar(32) | NO | MUL | NULL |  |
| doc_num | int | NO | MUL | NULL |  |
| token_num | int | NO | MUL | NULL |  |
| chunk_num | int | NO | MUL | NULL |  |
| similarity_threshold | float | NO | MUL | NULL |  |
| vector_similarity_weight | float | NO | MUL | NULL |  |
| parser_id | varchar(32) | NO | MUL | NULL |  |
| parser_config | longtext | NO |  | NULL |  |
| pagerank | int | NO |  | NULL |  |
| status | varchar(1) | YES | MUL | NULL |  |

## `llm`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| llm_name | varchar(128) | NO | PRI | NULL |  |
| model_type | varchar(128) | NO | MUL | NULL |  |
| fid | varchar(128) | NO | PRI | NULL |  |
| max_tokens | int | NO |  | NULL |  |
| tags | varchar(255) | NO | MUL | NULL |  |
| status | varchar(1) | YES | MUL | NULL |  |

## `llm_factories`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| name | varchar(128) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| logo | text | YES |  | NULL |  |
| tags | varchar(255) | NO | MUL | NULL |  |
| status | varchar(1) | YES | MUL | NULL |  |

## `task`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| doc_id | varchar(32) | NO | MUL | NULL |  |
| from_page | int | NO |  | NULL |  |
| to_page | int | NO |  | NULL |  |
| task_type | varchar(32) | NO |  | NULL |  |
| begin_at | datetime | YES | MUL | NULL |  |
| process_duation | float | NO |  | NULL |  |
| progress | float | NO | MUL | NULL |  |
| progress_msg | text | YES |  | NULL |  |
| retry_count | int | NO |  | NULL |  |
| digest | text | YES |  | NULL |  |
| chunk_ids | longtext | YES |  | NULL |  |

## `tenant`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| name | varchar(100) | YES | MUL | NULL |  |
| public_key | varchar(255) | YES | MUL | NULL |  |
| llm_id | varchar(128) | NO | MUL | NULL |  |
| embd_id | varchar(128) | NO | MUL | NULL |  |
| asr_id | varchar(128) | NO | MUL | NULL |  |
| img2txt_id | varchar(128) | NO | MUL | NULL |  |
| rerank_id | varchar(128) | NO | MUL | NULL |  |
| tts_id | varchar(256) | YES | MUL | NULL |  |
| parser_ids | varchar(256) | NO | MUL | NULL |  |
| credit | int | NO | MUL | NULL |  |
| status | varchar(1) | YES | MUL | NULL |  |

## `tenant_llm`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| tenant_id | varchar(32) | NO | PRI | NULL |  |
| llm_factory | varchar(128) | NO | PRI | NULL |  |
| model_type | varchar(128) | YES | MUL | NULL |  |
| llm_name | varchar(128) | NO | PRI | NULL |  |
| api_key | varchar(1024) | YES | MUL | NULL |  |
| api_base | varchar(255) | YES |  | NULL |  |
| max_tokens | int | NO | MUL | NULL |  |
| used_tokens | int | NO | MUL | NULL |  |

## `user`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| access_token | varchar(255) | YES | MUL | NULL |  |
| nickname | varchar(100) | NO | MUL | NULL |  |
| password | varchar(255) | YES | MUL | NULL |  |
| email | varchar(255) | NO | MUL | NULL |  |
| avatar | text | YES |  | NULL |  |
| language | varchar(32) | YES | MUL | NULL |  |
| color_schema | varchar(32) | YES | MUL | NULL |  |
| timezone | varchar(64) | YES | MUL | NULL |  |
| last_login_time | datetime | YES | MUL | NULL |  |
| is_authenticated | varchar(1) | NO | MUL | NULL |  |
| is_active | varchar(1) | NO | MUL | NULL |  |
| is_anonymous | varchar(1) | NO | MUL | NULL |  |
| login_channel | varchar(255) | YES | MUL | NULL |  |
| status | varchar(1) | YES | MUL | NULL |  |
| is_superuser | tinyint(1) | YES | MUL | NULL |  |
| is_system | tinyint(1) | YES | MUL | NULL |  |

## `user_canvas`

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
| dsl | longtext | YES |  | NULL |  |

## `user_class`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| user_id | varchar(32) | NO | MUL | NULL |  |
| class_id | varchar(32) | NO | MUL | NULL |  |
| role | varchar(32) | NO | MUL | NULL |  |
| status | varchar(1) | YES | MUL | NULL |  |

## `user_tenant`

| Field | Type | Null | Key | Default | Extra |
|-------|------|------|-----|---------|-------|
| id | varchar(32) | NO | PRI | NULL |  |
| create_time | bigint | YES | MUL | NULL |  |
| create_date | datetime | YES | MUL | NULL |  |
| update_time | bigint | YES | MUL | NULL |  |
| update_date | datetime | YES | MUL | NULL |  |
| user_id | varchar(32) | NO | MUL | NULL |  |
| tenant_id | varchar(32) | NO | MUL | NULL |  |
| role | varchar(32) | NO | MUL | NULL |  |
| invited_by | varchar(32) | NO | MUL | NULL |  |
| status | varchar(1) | YES | MUL | NULL |  |
