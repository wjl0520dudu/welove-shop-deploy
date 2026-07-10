package com.welove.shop.user.config;

import com.welove.shop.common.security.config.JwtProperties;
import com.welove.shop.common.security.interceptor.JwtInterceptor;
import com.welove.shop.common.security.jwt.JwtUtil;
import org.springframework.context.annotation.Configuration;
import org.springframework.lang.NonNull;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.List;

/**
 * user-service Web 配置:注册 JWT 拦截器 + 白名单。
 * <p>
 * 白名单命中的路径无需登录即可访问,其他所有 /api/** 必须携带有效 token。
 */
@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    private final JwtUtil jwtUtil;
    private final JwtProperties jwtProperties;

    /** 免鉴权路径。 */
    private static final List<String> WHITELIST = List.of(
            "/api/auth/sendCode",
            "/api/auth/login",
            "/api/auth/refresh",
            "/api/internal/**",          // 服务间 Feign 调用(骨架期免登录,Ph 后期与 Gateway 分层鉴权收窄)
            "/actuator/**",
            "/error"
    );

    public WebMvcConfig(JwtUtil jwtUtil, JwtProperties jwtProperties) {
        this.jwtUtil = jwtUtil;
        this.jwtProperties = jwtProperties;
    }

    @Override
    public void addInterceptors(@NonNull InterceptorRegistry registry) {
        JwtInterceptor interceptor = new JwtInterceptor(jwtUtil, jwtProperties.getHeader(), WHITELIST);
        registry.addInterceptor(interceptor)
                .addPathPatterns("/api/**")
                .excludePathPatterns(WHITELIST);
    }
}
