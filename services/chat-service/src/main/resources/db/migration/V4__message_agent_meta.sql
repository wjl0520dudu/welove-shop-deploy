-- Persist the visible DAG plan/execution summary so H5 can render it after a reload.
SET search_path TO chat_svc;

ALTER TABLE message ADD COLUMN agent_meta JSONB;
