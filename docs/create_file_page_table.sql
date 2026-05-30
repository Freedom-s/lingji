-- 创建 file_page 表
-- 用于存储文件页面图片的元数据

CREATE TABLE IF NOT EXISTS `file_page` (
    `id` VARCHAR(32) NOT NULL COMMENT '主键ID',
    `file_id` VARCHAR(32) NOT NULL COMMENT '关联file表的ID',
    `page_number` INT NOT NULL COMMENT '页码（从1开始）',
    `location` VARCHAR(255) NOT NULL COMMENT 'MinIO存储路径',
    `size` INT DEFAULT 0 COMMENT '图片大小（字节）',
    `width` INT DEFAULT 0 COMMENT '图片宽度（像素）',
    `height` INT DEFAULT 0 COMMENT '图片高度（像素）',
    `format` VARCHAR(16) DEFAULT 'JPEG' COMMENT '图片格式',
    `create_time` BIGINT DEFAULT NULL COMMENT '创建时间戳',
    `create_date` DATETIME DEFAULT NULL COMMENT '创建日期',
    `update_time` BIGINT DEFAULT NULL COMMENT '更新时间戳',
    `update_date` DATETIME DEFAULT NULL COMMENT '更新日期',
    PRIMARY KEY (`id`),
    INDEX `idx_file_id` (`file_id`),
    INDEX `idx_page_number` (`page_number`),
    INDEX `idx_create_time` (`create_time`),
    INDEX `idx_create_date` (`create_date`),
    INDEX `idx_update_time` (`update_time`),
    INDEX `idx_update_date` (`update_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='文件页面表';

-- 查看表结构
DESC file_page;

-- 查看索引
SHOW INDEX FROM file_page;
