package com.welove.shop.common.security.interceptor;

import com.welove.shop.common.core.exception.BizException;
import com.welove.shop.common.core.exception.ErrorCode;
import com.welove.shop.common.security.context.UserContext;
import com.welove.shop.common.security.jwt.JwtUtil;
import io.jsonwebtoken.Claims;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.lang.NonNull;
import org.springframework.lang.Nullable;
import org.springframework.util.AntPathMatcher;
import org.springframework.web.servlet.HandlerInterceptor;

import java.util.List;

/**
 * JWT 鉴权拦截器。
 * <p>
 * 从请求头(默认 Authorization)解析 token,写入 {@link UserContext};失败抛 {@link BizException}
 * 由全局异常处理器转成 {@code 401 UNAUTHORIZED} 的 Result。
 * <p>
 * 白名单支持 Ant 通配符,如:
 * <pre>
 *   /api/auth/login
 *   /api/auth/**
 *   /actuator/**
 * </pre>
 * 白名单命中的请求直接放行,不解析 token。
 */
public class JwtInterceptor implements HandlerInterceptor {

    private static final Logger log = LoggerFactory.getLogger(JwtInterceptor.class);
    private static final AntPathMatcher MATCHER = new AntPathMatcher();

    private final JwtUtil jwtUtil;
    private final String headerName;
    private final List<String> whitelist;

    public JwtInterceptor(JwtUtil jwtUtil, String headerName, List<String> whitelist) {
        this.jwtUtil = jwtUtil;
        this.headerName = headerName;
        this.whitelist = whitelist == null ? List.of() : whitelist;
    }

    @Override
    public boolean preHandle(@NonNull HttpServletRequest request,
                             @NonNull HttpServletResponse response,
                             @NonNull Object handler) {
        // OPTIONS 预检直接放行
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            return true;
        }

        String path = request.getRequestURI();
        for (String pattern : whitelist) {
            if (MATCHER.match(pattern, path)) {
                return true;
            }
        }

        String headerValue = request.getHeader(headerName);
        String token = jwtUtil.stripPrefix(headerValue);
        if (token == null || token.isEmpty()) {
            throw new BizException(ErrorCode.UNAUTHORIZED);
        }

        Claims claims;
        try {
            claims = jwtUtil.parse(token);
        } catch (Exception e) {
            log.debug("jwt parse failed for {} {}: {}", request.getMethod(), path, e.getMessage());
            throw new BizException(ErrorCode.UNAUTHORIZED);
        }

        Long userId = Long.parseLong(claims.getSubject());
        String username = claims.get("username", String.class);
        String phone = claims.get("phone", String.class);
        String role = claims.get("role", String.class);

        UserContext.set(new UserContext.UserPrincipal(userId, username, phone, role));
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
