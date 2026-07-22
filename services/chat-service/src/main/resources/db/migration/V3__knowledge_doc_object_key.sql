-- chat-service Flyway V3: knowledge_doc 表加 object_key 字段,
-- 用于支持云存储(阿里云 OSS)接入。
--
-- 设计:
--   file_path   = 对外可访问的完整 URL(Bucket 公共读模式直接拼域名,或 CDN 域名)
--                 兼容历史:旧数据里存的是相对路径(留作回退渲染兜底)
--   object_key  = 对象存储内部的 key,用于删除/查重(新增,可空,旧数据为 NULL)
--
-- 删除文件(知识库下线)走 object_key 调 storageService.delete(key),
-- 不再依赖解析 file_path。
--
-- 索引可选:暂不加 — knowledge_doc 行数小,先观察。

SET search_path TO chat_svc;

ALTER TABLE knowledge_doc
    ADD COLUMN object_key VARCHAR(512);
