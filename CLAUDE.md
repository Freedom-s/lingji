# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RAGFlow-Plus is an enhanced RAG (Retrieval-Augmented Generation) system based on RAGFlow, designed for Chinese application scenarios (高校 AI 助学平台). It has a dual-system architecture: a **前台 (Frontend)** for teachers and students to interact with AI assistants, and a **后台 (Management)** for teachers to manage classes, students, assistants, files, and view analytics.

### System Architecture & Role Design

```
┌─────────────────────────────────────────────────────────────┐
│  前台 (Frontend) — 师生共用                                    │
│  ┌─────────────────────┐  ┌──────────────────────────────┐  │
│  │ web/ (React + Umi 4) │  │ api/ (Flask, port 9380)       │  │
│  │ 教师 & 学生           │  │ /v1/conversation/*             │  │
│  │ - 助教中心             │  │ /v1/dialog/*                   │  │
│  │ - 知识库浏览            │  │ /v1/document/*                 │  │
│  │ - AI 对话              │  │ /v1/chunk/*                   │  │
│  │ - 课件学习 (/learning)  │  │ /v1/kb/*                      │  │
│  └─────────────────────┘  └──────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  后台 (Management) — 教师专用                                  │
│  ┌──────────────────────────┐  ┌──────────────────────────┐ │
│  │ management/web/           │  │ management/server/        │ │
│  │ (Vue 3 + Element Plus)   │  │ (Flask, port 5000)        │ │
│  │ 仅教师 (is_superuser=1)   │  │ /api/v1/dashboard/*        │ │
│  │ - 数据概览 (ECharts)      │  │ /api/v1/teams/* (班级)      │ │
│  │ - 学生管理                │  │ /api/v1/users/* (学生)      │ │
│  │ - 班级管理                │  │ /api/v1/assistants/* (助教) │ │
│  │ - 助教管理                │  │ /api/v1/files/* (教学文件)   │ │
│  │ - 教学文件管理            │  │ /api/v1/knowledgebases/*     │ │
│  │ - 知识库管理              │  │ /api/v1/conversation/*       │ │
│  │ - 学生会话管理            │  │ /api/v1/teachers/*           │ │
│  └──────────────────────────┘  └──────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  共享基础设施                                                  │
│  MySQL (rag_flow DB) | Redis | MinIO | Elasticsearch         │
│  rag/ (RAG Engine) | graphrag/ (GraphRAG)                    │
└─────────────────────────────────────────────────────────────┘
```

**前台和后端共用同一个 `rag_flow` 数据库**，但通过不同的后端服务访问：
- **api/** 使用 Peewee ORM 操作数据库，端口 9380
- **management/server/** 使用 mysql.connector 原生 SQL 操作数据库，端口 5000

两者认证系统独立：前台用 Flask-Login session，后台用 JWT token。

## Development Commands — 启动开发环境

开发时需要启动 **4 个服务**（每个在单独的终端窗口中运行）：

### 1. 前台后端 API Server (端口 9380)

```bash
conda activate ragflowplus
python -m api.ragflow_server
```

### 2. 前台前端 Web (端口 9222)

```bash
cd web
npm run dev
```

### 3. 后台后端 Management Server (端口 5000)

```bash
cd management/server
python app.py
```

### 4. 后台前端 Management Web (端口 8888)

```bash
cd management/web
npm run dev
```

### 开发访问地址

| 系统 | URL | 用户 |
|------|-----|------|
| 前台登录 | http://localhost:9222/login | teacher1@qq.com / teacher1 |
| 后台登录 | http://localhost:8888 | teacher1@qq.com / teacher1 |

---

## Architecture Details

### 前台 Backend (`api/`)

- **Framework**: Flask, port 9380
- **Auth**: Flask-Login (session-based)
- **ORM**: Peewee (`api/db/db_models.py`)
- **Task Queue**: Redis (document parsing, embedding, indexing)
- **Entry**: `api/ragflow_server.py` → `api/apps/__init__.py` (register blueprints)

**Route Blueprints** (`api/apps/`):
| File | Prefix | Description |
|------|--------|-------------|
| `conversation_app.py` | `/v1/conversation/` | Chat completion (SSE), conversation CRUD, message feedback |
| `dialog_app.py` | `/v1/dialog/` | Teaching assistant CRUD, class-based access control |
| `document_app.py` | `/v1/document/` | Document upload, parse, list, download |
| `chunk_app.py` | `/v1/chunk/` | Page-level chunk listing, retrieval test |
| `kb_app.py` | `/v1/kb/` | Knowledge base CRUD |
| `api_app.py` | `/api/` | Token management, stats (tenant-level) |
| `user_app.py` | `/v1/user/` | User info, tenant info |
| `file_app.py` | `/v1/file/` | File manager |
| `canvas_app.py` | `/v1/canvas/` | Canvas/flow editor |
| `learning_stats_app.py` | `/v1/learning_stats/` | Learning stats (dialog progress, quiz results, streak) |
| `system_app.py` | `/v1/system/` | System status, version |

### 前台 Frontend (`web/`)

- **Framework**: React 18 + TypeScript + Umi 4 + Ant Design 5 + Tailwind CSS
- **State**: Zustand (global), React Query (server state)
- **Build**: pnpm
- **Routes**: `web/src/routes.ts`

**Key Routes**:
| Route | Page | Users |
|-------|------|-------|
| `/chat` | AI Chat | 师生 |
| `/teaching-assistant` | 助教中心 | 师生 |
| `/learning` | 课件学习 (分屏: PPT + 对话) | 学生 |
| `/knowledge` | 知识库管理 | 师生 |
| `/file` | 文件管理 | 师生 |
| `/user-setting` | 用户设置 | 师生 |
| `/search` | 搜索 | 师生 |

### 后台 Backend (`management/server/`)

- **Framework**: Flask, port 5000
- **Auth**: JWT (HS256), `@require_superuser` decorator
- **DB**: mysql.connector (raw SQL, NO ORM)
- **Entry**: `management/server/app.py`

**Route Blueprints** (`management/server/routes/`):
| File | Prefix | Description |
|------|--------|-------------|
| `dashboard/routes.py` | `/api/v1/dashboard` | 数据概览, 活跃趋势, 助教排行, 班级排行 |
| `teams/routes.py` | `/api/v1/teams` | 班级 CRUD, 成员管理, 班级助教 |
| `users/routes.py` | `/api/v1/users` | 学生 CRUD |
| `teachers/routes.py` | `/api/v1/teachers` | 教师 CRUD (需 system admin) |
| `assistants/routes.py` | `/api/v1/assistants` | 助教 CRUD |
| `files/routes.py` | `/api/v1/files` | 教学文件上传/下载/删除 |
| `knowledgebases/routes.py` | `/api/v1/knowledgebases` | 知识库管理, 文档解析 |
| `conversation/routes.py` | `/api/v1/conversation` | 查看学生对话 |
| `tenants/routes.py` | `/api/v1/tenants` | 租户管理 |

### 后台 Frontend (`management/web/`)

- **Framework**: Vue 3.5 + TypeScript + Vite 6 + Element Plus 2 + ECharts 6 + Pinia 3
- **Template**: v3-admin-vite (Vue3 admin template)
- **State**: Pinia (stores: user, permission, app, settings, tags-view)
- **Router**: vue-router 4 (constantRoutes + dynamicRoutes)

**Key Pages** (`management/web/src/pages/`):
| Directory | Title | Description |
|-----------|-------|-------------|
| `dashboard/` | 数据概览 | ECharts: 概览卡片, 活跃趋势, 对话趋势, 助教排行, 班级排行 |
| `user-management/` | 学生管理 | 学生 CRUD 表格 |
| `team-management/` | 班级管理 | 班级 CRUD, 成员/助教关联 |
| `teacher-management/` | 教师管理 | 教师 CRUD (仅 system admin 可见) |
| `assistant-management/` | 助教管理 | 助教 (dialog) CRUD |
| `file/` | 教学文件管理 | 文件上传/预览/下载 |
| `knowledgebase/` | 知识库管理 | KB CRUD, 文档管理 |
| `conversation/` | 学生会话 | 查看学生对话记录 |
| `login/` | 登录 | JWT 认证 |

**API Client** (`management/web/src/common/apis/`): Each domain has `index.ts` (functions) + `type.ts` (TypeScript interfaces).

---

## Database

### Shared Database

Both `api/` and `management/server/` connect to the same `rag_flow` MySQL database. Full schema (27 tables) is documented in `docs/database_schema.md`.

配置来源为 `docker/.env`：

| 服务 | Host | Port | User | Password | Database |
|------|------|------|------|----------|----------|
| MySQL | 127.0.0.1 (Docker内: mysql) | 5455 | root | infini_rag_flow | rag_flow |
| Elasticsearch | 127.0.0.1 (Docker内: es01) | 1200 | elastic | infini_rag_flow | — |

**连接命令：**

MySQL（本地未安装 mysql 客户端，通过 Docker 容器执行）：
```bash
docker exec ragflow-mysql mysql -u root -pinfini_rag_flow rag_flow -e "<SQL>"
```

Elasticsearch：
```bash
# 列出所有索引
curl -s -u elastic:infini_rag_flow 'http://localhost:1200/_cat/indices?v'
# 查看索引 mapping
curl -s -u elastic:infini_rag_flow 'http://localhost:1200/<index>/_mapping'
# 搜索文档
curl -s -u elastic:infini_rag_flow 'http://localhost:1200/<index>/_search?size=5'
```

> **原则：当任务需要了解数据时，必须实际连接数据库查看表结构和数据，不要凭空猜测。**

**Key tables for class-based access control:**
- `class` — 班级
- `user_class` — 用户-班级关联 (含 role: teacher/student)
- `class_dialog` — 班级-助教关联
- `user` — 用户 (is_superuser=1 表示老师)

**Key tables for education/learning features (RAGFlow-Plus 新增):**
- `document_generation` — 文档生成的课件内容 (quiz/mindmap/flashcards)，JSON 格式
- `student_quiz_result` — 学生测验答题记录 (student_id, doc_id, question_index, student_answer, is_correct)
- `knowledge_point_mastery` — 知识点掌握度追踪 (SM-2 间隔重复算法: correct_count, wrong_count, next_review_time, ease_factor)
- `student_card_progress` — 闪卡学习进度 (card_index, status: remembered/forgotten/learning)
- `student_note` — 学生在文档上的笔记 (doc_id, page_number, content)

### Storage Architecture

| 服务 | Host | Port | User | Password |
|------|------|------|------|----------|
| **Document Store** (ES) | 127.0.0.1 (Docker内: es01) | 1200 | elastic | infini_rag_flow |
| **Object Storage** (MinIO) | 127.0.0.1 (Docker内: minio) | API: 9000, Console: 9001 | rag_flow | infini_rag_flow |
| **Database** (MySQL) | 127.0.0.1 (Docker内: mysql) | 5455 | root | infini_rag_flow |
| **Cache/Queue** (Redis) | 127.0.0.1 (Docker内: redis) | 6379 | — | infini_rag_flow |

- Document Store 可选 Infinity (`DOC_ENGINE` env var)
- Object Storage 可选 S3, Azure, Alibaba OSS
- Database 可选 PostgreSQL
- MySQL: `api/` 用 Peewee ORM, `management/server/` 用 mysql.connector 原生 SQL

### LLM Integration

The system supports multiple LLM providers through factories configured in `conf/llm_factories.json`:
- OpenAI, Anthropic, Azure OpenAI, Google Gemini
- Tongyi Qianwen, Zhipu AI, Tencent Cloud
- Local models via Ollama
- And 15+ other providers

Model types: chat, embedding, rerank, ASR, image2text

---

## Key File Locations

### 前台 Backend (api/)
- `api/ragflow_server.py` — HTTP API server entry
- `api/apps/__init__.py` — Flask app initialization and route registration
- `api/apps/` — API endpoint handlers
- `api/db/db_models.py` — Peewee ORM models
- `api/db/services/` — Database service layer
- `rag/svr/task_executor.py` — Background task processor
- `rag/nlp/search.py` — Retrieval logic (Dealer class)
- `rag/llm/` — LLM model abstractions
- `rag/app/` — Document parsers
- `graphrag/search.py` — GraphRAG retrieval

### 前台 Frontend (web/)
- `web/src/routes.ts` — Route configuration
- `web/src/pages/` — Page components
- `web/src/components/` — Reusable components
- `web/src/hooks/` — Custom React hooks
- `web/src/utils/` — Utilities
- `web/src/interfaces/` — TypeScript interfaces

### 后台 Backend (management/server/)
- `management/server/app.py` — Management server entry
- `management/server/auth.py` — JWT auth decorators
- `management/server/database.py` — MySQL/MinIO/ES/Redis connections
- `management/server/routes/` — Route blueprints
- `management/server/services/` — Service layer (raw SQL)

### 后台 Frontend (management/web/)
- `management/web/src/router/` — Vue Router config
- `management/web/src/pages/` — Page components (Vue SFC)
- `management/web/src/pinia/stores/` — Pinia state stores
- `management/web/src/common/apis/` — API client functions + types
- `management/web/src/layouts/` — Layout + Sidebar

---

## Configuration

### Backend Configuration

Primary configuration is in `conf/service_conf.yaml` (generated from `docker/service_conf.yaml.template` at startup):
- `ragflow`: HTTP server settings (host, port)
- `mysql`/`postgres`: Database connection
- `minio`: Object storage for files
- `es`/`infinity`: Document storage engine
- `redis`: Cache and task queue
- `user_default_llm`: Default LLM models

Environment variables override template values (e.g., `MYSQL_HOST`, `MINIO_PASSWORD`).

### Frontend Configuration
- `web/.umirc.ts`: Umi build configuration (proxy `/api` and `/v1` to `http://127.0.0.1:9380`)
- `web/src/conf.json`: Runtime configuration (API endpoints, feature flags)

### Management Configuration
- `management/server/`: Reads from `docker/.env` for DB credentials
- `management/web/`: Vite proxy in `vite.config.ts`

---

## Development Notes

### Adding New Document Parsers
1. Create parser in `rag/app/your_parser.py`
2. Add to `FACTORY` dict in `rag/svr/task_executor.py`
3. Add `ParserType` enum value in `api/db/db_models.py`
4. Register in default parsers list in `api/settings.py` (PARSERS variable)

### Adding New LLM Providers
1. Add provider configuration to `conf/llm_factories.json`
2. Implement factory class in `rag/llm/` if custom behavior needed
3. Add to supported factories in `api/db/init_data.py`

### 前台 Frontend Development
- Uses Umi 4 convention for routing (file-based routing in `src/pages/`)
- State management: Zustand for global state, React Query for server state
- Styling: Tailwind CSS utility classes preferred, Less modules for complex styles
- API calls: via `umi-request` with proxy configuration

### 后台 Frontend Development
- Uses Vue 3 Composition API (`<script setup lang="ts">`)
- State management: Pinia stores
- UI: Element Plus components (el-table, el-form, el-dialog, etc.)
- Charts: ECharts via vue-echarts
- API calls: axios with JWT token in header (`Authorization: Bearer <token>`)
- Access control: `@require_superuser` on backend routes, `permissionStore` for frontend route visibility

### Task Processing
Tasks are queued to Redis and consumed by task executor workers. Task types:
- Document parsing and chunking
- Embedding generation
- GraphRAG indexing
- Agentic reasoning workflows

Max concurrent tasks controlled by `MAX_CONCURRENT_TASKS` environment variable.

---

## Code Quality

- Python: Ruff linter configured (line length: 200)
- TypeScript (前台): ESLint + Prettier configured
- TypeScript (后台): ESLint + Prettier configured
- Pre-commit hooks via Husky for frontend

---

## Important Environment Variables

- `DB_TYPE`: mysql or postgres
- `DOC_ENGINE`: elasticsearch or infinity
- `MAX_CONCURRENT_TASKS`: Max parallel background tasks
- `WS`: Number of task executor workers
- `LIGHTEN`: Enable lightweight mode (1=enabled)
- `MINIO_VISIT_HOST`, `MINIO_PORT`: MinIO public endpoint

---
