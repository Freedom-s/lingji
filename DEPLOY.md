# 部署说明（RAGFlow-Plus 生产环境）

本文档说明如何把本仓库的代码部署到生产节点 **songsen**（10.18.21.55）。

> 适用对象：需要发布代码、排查线上问题、或把环境迁移到新机器的维护者。
> 本地开发启动方式见 `CLAUDE.md` 的「Development Commands」章节，本文只讲**生产部署**。

---

## 一、拓扑总览

```
开发机 (Mac)
   │  ./deploy.sh <组件>
   │  ssh songsen (10.18.21.55, 用户 user)
   ▼
songsen —— 应用 + 数据节点，代码在 /home/user/jianhuasuo/lingji
   ├─ 后端  conda 环境 lingji (/home/user/anaconda3/envs/lingji, Python 3.10)
   │     ├─ ragflow-api         (9380)  systemd 守护 → python -m api.ragflow_server
   │     └─ ragflow-management  (5000)  systemd 守护 → python app.py (management/server)
   ├─ 前端  nginx 托管
   │     ├─ 学生端  web/dist             → 端口 80
   │     └─ 教师端  management/web/dist  → 端口 8080
   └─ 数据  Docker 容器：MySQL(5455) / MinIO(9000) / Redis(6379) + ES(1200)
```

四个服务是「双前端 + 双后端」：

| 组件 | deploy.sh 参数 | 代码目录 | 运行方式 | 端口 |
|------|----------------|----------|----------|------|
| 前台前端（学生端） | `web` | `web/dist` | nginx | 80 |
| 后台前端（教师端） | `mgmt-web` | `management/web/dist` | nginx | 8080 |
| 前台后端 API | `api` | `api/` | systemd `ragflow-api` | 9380 |
| 后台后端管理 | `mgmt-server` | `management/server/` | systemd `ragflow-management` | 5000 |
| （依赖目录） | `infra` | `rag/` `graphrag/` `conf/` | — | — |

---

## 二、一次性准备（新成员 / 换机器才需要）

这些只需配置一次，之后日常部署不用再管。

### 1. SSH 免密别名 `songsen`

在本机 `~/.ssh/config` 里加：

```
Host songsen
    HostName 10.18.21.55
    User user
    IdentityFile ~/.ssh/id_rsa
```

验证：`ssh songsen "echo ok"` 能直接返回，不要求输密码。

### 2. sudo 密码文件 `.deploy.env`（已 git 忽略）

`deploy.sh` 重启 systemd / reload nginx 需要 root 权限，通过 `sudo -S` 从 ssh 远程执行。
把 sudo 密码写进仓库根目录的 `.deploy.env`：

```bash
echo 'SONGSEN_SUDO_PASS=你的sudo密码' > .deploy.env
```

> ⚠️ 该文件已加入 `.gitignore`，**绝不能提交到仓库**，也别把明文密码写进任何文档。
> 没有这个文件时，脚本会退化为 `ssh -t` 交互式 sudo，需要手动输密码。

### 3. 后端 Python 依赖

新增 pip 依赖时，`deploy.sh` **不会**自动装。需要在 songsen 上手动执行：

```bash
ssh songsen "source /home/user/anaconda3/etc/profile.d/conda.sh && conda activate lingji && pip install <包名>"
```

### 4. 数据库 / 存储凭据

后端读取 `docker/.env` 里的 MySQL / MinIO / ES / Redis 连接配置，通常无需改动。
需要查库时用（MySQL 走容器）：

```bash
ssh songsen "docker exec ragflow-mysql mysql -u root -pinfini_rag_flow rag_flow -e '<SQL>'"
```

---

## 三、日常部署

在仓库根目录执行：

```bash
./deploy.sh web          # 前台前端：npm build → 推 web/dist → reload nginx
./deploy.sh mgmt-web     # 后台前端：npm build → 推 management/web/dist → reload nginx
./deploy.sh api          # 前台后端：推 api/ → restart ragflow-api
./deploy.sh mgmt-server  # 后台后端：推 management/server/ → restart ragflow-management
./deploy.sh infra        # 依赖目录 rag/ graphrag/ conf/ → restart ragflow-api（改了才需要）
./deploy.sh all          # 以上四个一起（web + mgmt-web + api + mgmt-server）
```

改哪个就推哪个：

| 改了哪里的代码 | 用哪个命令 |
|----------------|------------|
| `web/src/`（学生端页面） | `./deploy.sh web` |
| `management/web/src/`（教师端页面） | `./deploy.sh mgmt-web` |
| `api/`（前台后端） | `./deploy.sh api` |
| `management/server/`（后台后端） | `./deploy.sh mgmt-server` |
| `rag/` `graphrag/` `conf/`（解析/检索/配置） | `./deploy.sh infra` |

### 脚本做了什么

- **前端**（`web` / `mgmt-web`）：本地 `npm run build` → `rsync --delete` 推 dist（`--delete` 会清掉旧的 hash 文件名）→ `systemctl reload nginx`。
- **后端**（`api` / `mgmt-server`）：`rsync` 增量覆盖代码（排除 `__pycache__` / `*.pyc`，mgmt-server 另排除 `logs`）→ `systemctl restart`。
- **infra**：`rsync` 推 `rag/` `graphrag/` `conf/` → `restart ragflow-api`（api 运行时依赖这三处 import + 读配置，日常不必重推）。

脚本带 `set -euo pipefail`，任何一步失败会立即停止并返回非零退出码。

---

## 四、部署后自检（重要）

`systemctl restart` 只保证「重启指令发出成功」，**不保证进程真的起来了**（后端代码有语法/导入错误时会启动即崩，但 systemd 可能仍显示 active）。所以部署后务必确认服务真的在响应：

```bash
# 1. 服务是否 active
ssh songsen "systemctl is-active ragflow-api ragflow-management nginx"

# 2. 后端 HTTP 是否真的在响应
ssh songsen "curl -s -o /dev/null -w '%{http_code}' http://localhost:9380/v1/system/version"  # 期望 200
ssh songsen "curl -s -o /dev/null -w '%{http_code}' http://localhost:5000/"                    # 期望 404（无根路由，能响应即表示 Flask 起来了）

# 3. 看启动日志有无 Traceback
ssh songsen "ls -t /home/user/jianhuasuo/lingji/logs/ | head"
ssh songsen "tail -n 30 /home/user/jianhuasuo/lingji/logs/ragflow_api_<最新时间戳>.log"
```

- api 正常启动会打印 `Running on http://10.18.21.55:9380`。
- 日志尾部出现 `401 Unauthorized` 是正常的鉴权拒绝，不是启动错误。

---

## 五、运维常用命令

```bash
# 查看服务状态 / 日志
ssh songsen "systemctl status ragflow-api ragflow-management"
ssh songsen "journalctl -u ragflow-api -n 50 --no-pager"

# 手动重启（等价于 deploy.sh 里做的）
ssh songsen "echo '密码' | sudo -S systemctl restart ragflow-api"

# 看数据库 / ES / MinIO
ssh songsen "docker exec ragflow-mysql mysql -u root -pinfini_rag_flow rag_flow -e '<SQL>'"
ssh songsen "curl -s -u elastic:infini_rag_flow 'http://localhost:1200/_cat/indices?v'"
```

---

## 六、注意事项

1. **后端依赖不随部署走**：新增 pip 包必须在 songsen 手动装（见「二、3」）。
2. **infra 不常用**：`api` 运行时依赖 `rag/` `graphrag/` `conf/`，日常改业务代码不需要重推这三处，只有改了解析器、检索逻辑或配置模板时才用 `./deploy.sh infra`。
3. **前端要清旧产物**：dist 用 `--delete` 清旧 hash，避免浏览器缓存命中的旧 JS；后端增量覆盖**不加** `--delete`，避免误删日志等本地文件。
4. **GPU / LLM 服务不在本次部署范围**：embedding / rerank / OCR 跑在另一台 `lingji`（10.15.25.201），chat 走 siliconflow 外网 API。改这些要在对应机器上操作。
5. **安全**：`.deploy.env` 里的 sudo 密码、`docker/.env` 与 `conf/service_conf.yaml` 里的 API key 都是敏感信息，不要提交或外泄。
