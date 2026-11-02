-- RAGFlow-Plus 知识库级知识图谱（第一版）
-- 管理端首次访问知识图谱接口时也会幂等执行同样的建表语句。
-- 单独保留这份 SQL，方便后续统一迁移和运维核对。

CREATE TABLE IF NOT EXISTS knowledge_base_graph (
    id VARCHAR(64) NOT NULL,
    kb_id VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    version INT NOT NULL DEFAULT 0,
    draft_json LONGTEXT NULL,
    published_json LONGTEXT NULL,
    source_snapshot LONGTEXT NULL,
    created_by VARCHAR(64) NOT NULL,
    generated_at DATETIME NULL,
    published_at DATETIME NULL,
    create_time BIGINT NULL,
    update_time BIGINT NULL,
    create_date DATETIME NULL,
    update_date DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_knowledge_base_graph_kb (kb_id),
    KEY idx_knowledge_base_graph_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
