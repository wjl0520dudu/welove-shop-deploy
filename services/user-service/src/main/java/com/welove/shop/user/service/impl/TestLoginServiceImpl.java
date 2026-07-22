package com.welove.shop.user.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.welove.shop.user.entity.User;
import com.welove.shop.user.mapper.UserMapper;
import com.welove.shop.user.service.AuthService;
import com.welove.shop.user.service.TestLoginService;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 测试登录实现。
 * <p>
 * 5 个固定测试手机号共享池(19800000001~19800000005),轮询使用。
 * 每个账号的 username = "体验用户_xxxx",头像走默认占位,无真实数据。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class TestLoginServiceImpl implements TestLoginService {

    /** 测试账号池大小;同时也是轮询模数。 */
    private static final int POOL_SIZE = 5;

    /** 测试手机号前缀:198 是中国电信 11 号段(尚未大规模商用),做体验号池不容易与真实用户冲突。 */
    private static final String TEST_PHONE_PREFIX = "198";

    private static final String TEST_PASSWORD_PLACEHOLDER = "test-login-placeholder";

    /** 轮询下标,所有请求共享。 */
    private final AtomicInteger counter = new AtomicInteger(0);

    private final UserMapper userMapper;
    private final AuthService authService;
    private final PasswordEncoder passwordEncoder;

    /** 启动时预热:确保 5 个测试账号存在(DB 缓存预热,降低首次体验延迟)。 */
    @PostConstruct
    @Transactional
    public void warmup() {
        ensureTestAccounts();
    }

    @Override
    public Map<String, Object> testLogin() {
        // 1. 确保账号池完整(防御性:warmup 失败 / 被人手动删除的场景)
        ensureTestAccounts();

        // 2. 轮询选一个账号
        int idx = Math.floorMod(counter.incrementAndGet(), POOL_SIZE);
        String phone = TEST_PHONE_PREFIX + String.format("%09d", idx + 1);

        User user = userMapper.selectOne(
                new LambdaQueryWrapper<User>().eq(User::getPhone, phone));
        if (user == null) {
            // 极端并发场景:两个请求同时触发 ensureTestAccounts,只有一个写入成功;
            // 另一个的 select 查不到,再创建一次。
            user = createTestUser(phone);
        }
        if (user.getStatus() != null && user.getStatus() == 0) {
            // 测试账号不应该被禁用,但万一被运维手动禁用,跳过到下一个
            log.warn("[test-login] 测试账号 {} 被禁用,跳过", phone);
            return testLogin();   // 递归到下一个(最多 POOL_SIZE 次,实际不可能)
        }

        // 3. 更新最后登录时间
        user.setLastLoginAt(LocalDateTime.now());
        user.setUpdateTime(LocalDateTime.now());
        userMapper.updateById(user);

        log.info("[test-login] 体验用户登录: phone={}, userId={}", phone, user.getId());

        // 4. 复用 AuthService 的 token 生成逻辑(已提到接口上)
        return authService.generateTokenResponse(user);
    }

    // ---------- 私有 ----------

    /**
     * 检查 5 个测试账号是否都存在;不存在则创建。
     */
    private void ensureTestAccounts() {
        for (int i = 1; i <= POOL_SIZE; i++) {
            String phone = TEST_PHONE_PREFIX + String.format("%09d", i);
            boolean exists = userMapper.selectCount(
                    new LambdaQueryWrapper<User>().eq(User::getPhone, phone)) > 0;
            if (!exists) {
                createTestUser(phone);
            }
        }
    }

    private User createTestUser(String phone) {
        User user = new User();
        user.setPhone(phone);
        user.setUsername("体验用户_" + phone.substring(phone.length() - 4));
        user.setPassword(passwordEncoder.encode(TEST_PASSWORD_PLACEHOLDER));
        user.setGender(0);
        user.setStatus(1);
        user.setIsTest(true);
        LocalDateTime now = LocalDateTime.now();
        user.setCreateTime(now);
        user.setUpdateTime(now);
        userMapper.insert(user);
        log.info("[test-login] 创建测试账号: phone={}, userId={}", phone, user.getId());
        return user;
    }
}