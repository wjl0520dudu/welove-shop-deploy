package com.welove.shop.gateway.filter;

import com.welove.shop.common.core.exception.ErrorCode;
import com.welove.shop.common.security.config.JwtProperties;
import com.welove.shop.common.security.jwt.JwtUtil;
import com.welove.shop.gateway.config.GatewayAuthProperties;
import io.jsonwebtoken.Claims;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.util.AntPathMatcher;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;
import java.util.List;

/**
 * 分层鉴权核心 — Gateway 侧 JWT 校验 GlobalFilter。
 * <p>
 * 处理流程:
 * <ol>
 *   <li>OPTIONS 预检请求直接放行(CORS 已经处理过)</li>
 *   <li>路径命中 {@link GatewayAuthProperties#getWhitelist()} 白名单 → 放行</li>
 *   <li>其他请求必须携带有效 {@code Authorization: Bearer <token>}</li>
 *   <li>校验 JWT 签名 + 过期。失败返回 10002 UNAUTHORIZED,响应体是标准 Result JSON</li>
 *   <li>校验通过后,把 userId/username/role 塞进 request header (X-User-Id / X-Username / X-Role),
 *       透传给下游。下游服务的 JwtInterceptor 仍会解 Authorization,双重保险,零信任。</li>
 * </ol>
 * <p>
 * <b>与下游 JwtInterceptor 的关系:</b>
 * <ul>
 *   <li>骨架期:下游仍从 Authorization 解 JWT(未改动),Gateway 只做"预检+透传",不阻塞下游解析</li>
 *   <li>Ph 后期:下游改为优先信任 X-User-Id 头,减少一次 JWT 解析(留 TODO)</li>
 * </ul>
 */
@Slf4j
@Component
public class JwtAuthGlobalFilter implements GlobalFilter, Ordered {

    private static final AntPathMatcher MATCHER = new AntPathMatcher();
    /** Gateway 传给下游服务的用户身份 Header 名字(与业界惯例 X-User-Id 保持一致)。 */
    private static final String HEADER_USER_ID = "X-User-Id";
    private static final String HEADER_USERNAME = "X-Username";
    private static final String HEADER_ROLE = "X-Role";

    private final JwtUtil jwtUtil;
    private final JwtProperties jwtProps;
    private final GatewayAuthProperties authProps;

    public JwtAuthGlobalFilter(JwtUtil jwtUtil, JwtProperties jwtProps, GatewayAuthProperties authProps) {
        this.jwtUtil = jwtUtil;
        this.jwtProps = jwtProps;
        this.authProps = authProps;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();
        String path = request.getURI().getPath();

        // 1. CORS 预检直接放行
        if (HttpMethod.OPTIONS.equals(request.getMethod())) {
            return chain.filter(exchange);
        }

        // 2. 白名单放行
        List<String> whitelist = authProps.getWhitelist();
        if (whitelist != null) {
            for (String pattern : whitelist) {
                if (MATCHER.match(pattern, path)) {
                    return chain.filter(exchange);
                }
            }
        }

        // 3. 提取 token
        String header = request.getHeaders().getFirst(jwtProps.getHeader());
        String token = jwtUtil.stripPrefix(header);
        if (token == null || token.isEmpty()) {
            return unauthorized(exchange, "缺少 Authorization Bearer token");
        }

        // 4. 校验 + 解析
        Claims claims;
        try {
            claims = jwtUtil.parse(token);
        } catch (Exception e) {
            log.debug("[gateway-auth] jwt parse failed {} {}: {}",
                    request.getMethod(), path, e.getMessage());
            return unauthorized(exchange, "token 无效或已过期");
        }

        Long userId;
        try {
            userId = Long.parseLong(claims.getSubject());
        } catch (Exception e) {
            return unauthorized(exchange, "token subject 非法");
        }
        String username = claims.get("username", String.class);
        String role = claims.get("role", String.class);

        // 5. 塞 header 透传给下游
        ServerHttpRequest mutated = request.mutate()
                .header(HEADER_USER_ID, String.valueOf(userId))
                .header(HEADER_USERNAME, username == null ? "" : username)
                .header(HEADER_ROLE, role == null ? "" : role)
                .build();

        return chain.filter(exchange.mutate().request(mutated).build());
    }

    /** Gateway JWT 过滤在鉴权阶段执行,order 尽量靠前(-100)。 */
    @Override
    public int getOrder() {
        return -100;
    }

    /** 返回统一 401 Result JSON。 */
    private Mono<Void> unauthorized(ServerWebExchange exchange, String reason) {
        ServerHttpResponse response = exchange.getResponse();
        response.setStatusCode(HttpStatus.UNAUTHORIZED);
        response.getHeaders().setContentType(MediaType.APPLICATION_JSON);
        String body = String.format(
                "{\"code\":%d,\"message\":\"%s\",\"data\":null,\"success\":false}",
                ErrorCode.UNAUTHORIZED.getCode(), reason);
        return response.writeWith(
                Mono.just(response.bufferFactory().wrap(body.getBytes(StandardCharsets.UTF_8))));
    }
}
