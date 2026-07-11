-- chat-service Flyway V2: message 表加 status/stopped_reason/stopped_at 字段,
-- 用于支持「流式中止后保留截断回复」(豆包式体验)。
--
-- status 取值:
--   done      - 正常完成 (默认值,兼容历史数据)
--   streaming - 流式中(预留,目前 chat-service 不持久化中间态)
--   truncated - 客户端中止 / 服务端异常中断,保留已生成的部分
--   error     - 流式过程中出错

SET search_path TO chat_svc;

ALTER TABLE message
    ADD COLUMN status         VARCHAR(16) NOT NULL DEFAULT 'done',
    ADD COLUMN stopped_reason VARCHAR(32),
    ADD COLUMN stopped_at     TIMESTAMP;

CREATE INDEX idx_msg_status ON message(status);