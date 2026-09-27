# 数据迁移说明（离线 · U 盘）

从旧机器 **songsen**（10.18.21.55，已断网）把数据迁到新机器 **shiyanshi**（10.18.21.47）。

## 迁移范围

| 数据 | 迁移 | 方式 |
|------|------|------|
| MySQL `rag_flow` 库 | ✅ 必须 | `mysqldump` 导出 `.sql` → 导入 |
| MinIO（上传文件 + 页面图） | ✅ 必须 | 打包数据卷 → 解包 |
| Elasticsearch | ✅ 建议迁 | 打包数据卷 → 解包（见第五步） |
| Redis | ❌ 跳过 | 任务队列 + 缓存，自动重建 |

> 旧机器**断网**，因此全程只用宿主机自带的 `tar` + 容器里的 `mysqldump`，不依赖联网下载。
> U 盘容量：MinIO 里有视频源文件，总量约 2~5GB，ES 约 42MB，建议 **16GB+**。

> **为什么 ES 也要迁**：后台「解析」完成后会自动调大模型生成课件内容（思维导图/概念速记闪卡/随堂测验，见 `management/server/services/knowledgebases/document_parser.py:483-492` → `generate_all_for_document`）。如果跳过 ES 重新解析，会覆盖 `document_generation` 里已有的内容，并让学生已有的测验成绩、闪卡进度跟新生成内容对不上。ES 数据只有 1 个索引、527 个 chunk、42MB，直接迁成本很低。

---

## 第一步：旧机器（songsen）上导出

在旧机器终端直接执行。

### 1. 导出 MySQL

```bash
docker exec ragflow-mysql mysqldump -u root -pinfini_rag_flow \
  --single-transaction --routines --triggers --events \
  --default-character-set=utf8mb4 rag_flow > /tmp/rag_flow.sql
```

> `--default-character-set=utf8mb4` 必须加，否则中文文件名/内容会乱码。
> 生成 `/tmp/rag_flow.sql` 后，`ls -lh /tmp/rag_flow.sql` 确认大小不为 0。

### 2. 打包 MinIO 数据卷

先找到 MinIO 数据卷在宿主机上的目录：

```bash
docker inspect ragflow-minio --format '{{ range .Mounts }}{{ .Source }}{{ println }}{{ end }}'
```

记下输出的目录（通常是 `/var/lib/docker/volumes/xxx/_data` 或一个 bind mount 目录），下面记为 `<MINIO目录>`。然后打包：

```bash
sudo tar czf /tmp/minio_data.tar.gz -C <MINIO目录> .
```

> 一定要 `-C <MINIO目录> .` 打**目录内部**的内容（含 `.minio.sys` 元数据），不要打包成带外层目录的结构。
> 确认：`ls -lh /tmp/minio_data.tar.gz`。

---

## 第二步：U 盘拷贝

把三个文件拷进 U 盘：

- `/tmp/rag_flow.sql`
- `/tmp/minio_data.tar.gz`
- `/tmp/es_data.tar.gz`（见第五步）

---

## 第三步：新机器（shiyanshi）上导入

U 盘插新机器，文件放到 `/tmp/`。先停后端，避免导入时有并发读写：

```bash
sudo systemctl stop ragflow-api ragflow-management
```

### 1. 导入 MySQL

```bash
# 先删掉现有库、重建（保证干净导入）
docker exec -i ragflow-mysql mysql -u root -pinfini_rag_flow \
  -e "DROP DATABASE IF EXISTS rag_flow; CREATE DATABASE rag_flow CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 导入
docker exec -i ragflow-mysql mysql -u root -pinfini_rag_flow \
  --default-character-set=utf8mb4 rag_flow < /tmp/rag_flow.sql
```

### 2. 导入 MinIO

先拿到新机器 MinIO 数据卷目录（同样用 `docker inspect`）：

```bash
docker inspect ragflow-minio --format '{{ range .Mounts }}{{ .Source }}{{ println }}{{ end }}'
```

记下目录，下面记为 `<新MINIO目录>`，然后：

```bash
docker stop ragflow-minio
sudo tar xzf /tmp/minio_data.tar.gz -C <新MINIO目录>
docker start ragflow-minio
```

### 3. 导入 Elasticsearch

ES 数据卷在 shiyanshi 上是 `/var/lib/docker/volumes/docker_esdata01/_data`（可用 `docker inspect ragflow-es-01` 确认）。**关键：先清空再解包**，因为新 ES 已经启动过一次、卷里有它自己生成的 node 身份，不删会跟旧 data 里的 node UUID 冲突起不来。

```bash
docker stop ragflow-es-01
sudo rm -rf /var/lib/docker/volumes/docker_esdata01/_data/*
sudo tar xzf /tmp/es_data.tar.gz -C /var/lib/docker/volumes/docker_esdata01/_data
docker start ragflow-es-01

# 验证：应能看到 ragflow_ 开头的索引（旧机器是 1 个、527 个 doc）
curl -u elastic:infini_rag_flow 'http://localhost:1200/_cat/indices?v'
```

> ⚠️ 直接 tar 数据卷**要求旧 ES 也是 8.x**（8.11.3 读不了 7.x 的 data 目录）。旧机器上先确认：`docker exec ragflow-es-01 bin/elasticsearch --version`。若是 7.x，改用 snapshot/restore 而不是直接解包数据卷。

### 4. 启动后端

```bash
sudo systemctl start ragflow-api ragflow-management
```

---

## 第四步：验证

```bash
# MySQL：文档数量应与旧机器一致（之前是 19）
ssh shiyanshi "docker exec ragflow-mysql mysql -u root -pinfini_rag_flow rag_flow -N -e 'SELECT COUNT(*) FROM document'"

# MinIO：bucket 应该被自动恢复（bucket 名 = tenant_id）
ssh shiyanshi "docker exec ragflow-minio ls /data 2>/dev/null || docker exec ragflow-minio sh -c 'ls <新MINIO目录>'"

# ES：索引应已恢复（旧机器是 1 个 ragflow_ 开头的索引、527 个 doc）
ssh shiyanshi "curl -s -u elastic:infini_rag_flow 'http://localhost:1200/_cat/indices?v'"

# 后端是否起来
ssh shiyanshi "systemctl is-active ragflow-api ragflow-management"
```

> 关键点：MySQL 里的 `file.location`（形如 `<file_id>/source/xxx`）必须能在 MinIO 里找到对应对象。两边是同一台旧机器导出的，天然一致。

---

## 迁移完成后

MySQL + MinIO + ES 三者都迁完，文档保持「已解析」状态，**不需要重新解析**，学生已有的测验成绩、闪卡进度、笔记（都在 MySQL）不受影响。直接打开前台知识库确认能正常检索、文档状态正常即可。

> 如果发现个别文档检索不到，再单独对它重新解析（会重新调大模型生成课件内容），而不是全量重来。
