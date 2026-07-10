package com.welove.shop.admin.interceptor;

import com.welove.shop.admin.exception.AdminErrorCode;
import com.welove.shop.common.core.exception.BizException;
import com.welove.shop.common.core.exception.ErrorCode;
import com.welove.shop.common.security.context.UserContext;
import com.welove.shop.common.security.jwt.JwtUtil;
import io.jsonwebtoken.Claims;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.lang.NonNull;
import org.springframework.lang.Nullable;
import org.springframework.util.AntPathMatcher;
import org.springframework.web.servlet.HandlerInterceptor;

import java.util.List;

/**
 * Admin 鉴权拦截器。
 * <p>
 * 校验 JWT 有效性 + claims.role 必须为 "ADMIN"。
 * 非 ADMIN token 返回 60003 NOT_ADMIN_TOKEN。
 * <p>
 * 与 common-security 里的 {@link com.welove.shop.common.security.interceptor.JwtInterceptor}
 * 的区别:多了 role 校验。管理端专用。
 */
@Slf4j
public class AdminInterceptor implements HandlerInterceptor {

    private static final AntPathMatcher MATCHER = new AntPathMatcher();
    private final JwtUtil jwtUtil;
    private final String headerName;
    private final List<String> whitelist;

    public AdminInterceptor(JwtUtil jwtUtil, String headerName, List<String> whitelist) {
        this.jwtUtil = jwtUtil;
        this.headerName = headerName;
        this.whitelist = whitelist == null ? List.of() : whitelist;
    }

    @Override
    public boolean preHandle(@NonNull HttpServletRequest request,
                             @NonNull HttpServletResponse response,
                             @NonNull Object handler) {
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            return true;
        }
        String path = request.getRequestURI();
        for (String pattern : whitelist) {
            if (MATCHER.match(pattern, path)) return true;
        }
        String header = request.getHeader(headerName);
        String token = jwtUtil.stripPrefix(header);
        if (token == null || token.isEmpty()) {
            throw new BizException(ErrorCode.UNAUTHORIZED);
        }
        Claims claims;
        try {
            claims = jwtUtil.parse(token);
        } catch (Exception e) {
            throw new BizException(ErrorCode.UNAUTHORIZED);
        }
        String role = claims.get("role", String.class);
        if (!"ADMIN".equals(role)) {
            throw new BizException(AdminErrorCode.NOT_ADMIN_TOKEN, "非管理员 token");
        }
        Long userId = Long.parseLong(claims.getSubject());
        String username = claims.get("username", String.class);
        UserContext.set(new UserContext.UserPrincipal(userId, username, null, role));
        return true;
    }

    @Override
    public void afterCompletion(@NonNull HttpServletRequest request,
                                @NonNull HttpServletResponse response,
                                @NonNull Object handler,
                                @Nullable Exception ex) {
        UserContext.clear();
    }
}
