package com.welove.shop.admin.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.welove.shop.admin.dto.LoginRequest;
import com.welove.shop.admin.entity.Admin;
import com.welove.shop.admin.exception.AdminErrorCode;
import com.welove.shop.admin.mapper.AdminMapper;
import com.welove.shop.admin.service.AdminService;
import com.welove.shop.common.core.exception.BizException;
import com.welove.shop.common.security.jwt.JwtUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;

/**
 * 管理员登录服务。
 * <p>
 * 密码校验策略(对齐 monolith):
 * <ol>
 *   <li>优先 BCrypt matches;</li>
 *   <li>fallback:明文对比(兼容早期未 BCrypt 化的账号)。命中后自动升级为 BCrypt 写回。</li>
 * </ol>
 * <p>
 * JWT claims 里 {@code role=ADMIN},与 C 端用户 token 区分。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AdminServiceImpl implements AdminService {

    private final AdminMapper adminMapper;
    private final JwtUtil jwtUtil;
    private final PasswordEncoder passwordEncoder;

    @Override
    public Map<String, Object> login(LoginRequest request) {
        Admin admin = adminMapper.selectOne(
                new LambdaQueryWrapper<Admin>().eq(Admin::getUsername, request.getUsername()));
        if (admin == null) {
            throw new BizException(AdminErrorCode.INVALID_CREDENTIALS, "用户名或密码错误");
        }

        String raw = request.getPassword();
        boolean ok = false;
        try {
            ok = passwordEncoder.matches(raw, admin.getPassword());
        } catch (Exception ignore) {
            // BCrypt 格式异常,可能是明文密码
        }
        if (!ok && raw.equals(admin.getPassword())) {
            // 明文兼容:登录成功后自动升级为 BCrypt
            log.info("[Admin] 明文密码兼容登录,自动升级 BCrypt: userId={}", admin.getId());
            admin.setPassword(passwordEncoder.encode(raw));
            adminMapper.updateById(admin);
            ok = true;
        }
        if (!ok) {
            throw new BizException(AdminErrorCode.INVALID_CREDENTIALS, "用户名或密码错误");
        }

        // 签发 JWT,role=ADMIN
        Map<String, Object> claims = new HashMap<>();
        claims.put("username", admin.getUsername());
        claims.put("role", "ADMIN");
        String accessToken = jwtUtil.generateToken(admin.getId(), claims);
        String refreshToken = jwtUtil.generateRefreshToken(admin.getId());

        Map<String, Object> resp = new HashMap<>();
        resp.put("accessToken", accessToken);
        resp.put("refreshToken", refreshToken);
        resp.put("tokenType", "Bearer");
        resp.put("admin", admin);
        return resp;
    }
}
