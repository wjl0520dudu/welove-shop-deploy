-- =====================================================================
-- V2: 测试登录支持
-- 给 users 加两个字段:
--   is_test        — 测试账号标记,前端可据此显示"测试账号"角标
--   last_login_at  — 最后登录时间,供后续清理定时任务判断"长期未使用"
-- =====================================================================

SET search_path TO user_svc;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS is_test        BOOLEAN     NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS last_login_at  TIMESTAMP;

COMMENT ON COLUMN users.is_test       IS '是否测试账号(由 POST /auth/test-login 创建)';
COMMENT ON COLUMN users.last_login_at IS '最后登录时间,清理任务按 N 天未登录判定';

-- 索引:清理任务按 last_login_at + is_test 扫描
CREATE INDEX IF NOT EXISTS idx_users_is_test_last_login
    ON users(is_test, last_login_at)
    WHERE is_test = TRUE;