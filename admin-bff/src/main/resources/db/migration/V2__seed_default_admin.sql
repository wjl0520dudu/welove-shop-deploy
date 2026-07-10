-- =====================================================================
-- admin-bff V2:默认管理员账号
-- 默认用户名:admin
-- 默认密码:  admin123(BCrypt 加密后写入)
-- 首次登录建议尽快修改密码
-- =====================================================================

SET search_path TO admin_svc;

-- BCrypt(admin123, cost=10)
-- 由 BCryptPasswordEncoder.encode("admin123") 生成的一个静态值,便于 seed
INSERT INTO admin (username, password, role, create_time)
VALUES (
    'admin',
    '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy',
    'ADMIN',
    CURRENT_TIMESTAMP
);
