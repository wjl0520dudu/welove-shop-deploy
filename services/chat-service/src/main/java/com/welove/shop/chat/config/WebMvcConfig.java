package com.welove.shop.chat.config;

import com.welove.shop.common.security.config.JwtProperties;
import com.welove.shop.common.security.interceptor.JwtInterceptor;
import com.welove.shop.common.security.jwt.JwtUtil;
import org.springframework.context.annotation.Configuration;
import org.springframework.lang.NonNull;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.List;

/**
 * chat-service Web 配置:注册 JWT 拦截器 + 白名单(网关 StripPrefix=2 后收到的路径,无 /api 前缀)。
 */
@Configuration
public class WebMvcConfig implements WebMvcConfigurer {
    private final JwtUtil jwtUtil;
    private final JwtProperties jwtProperties;

    private static final List<String> WHITELIST = List.of(
            "/notice/latest",
            "/internal/**",    // 内部统计接口(admin-bff Dashboard Feign 调)
            "/actuator/**",
            "/error"
    );

    public WebMvcConfig(JwtUtil jwtUtil, JwtProperties jwtProperties) {
        this.jwtUtil = jwtUtil; this.jwtProperties = jwtProperties;
    }

    @Override
    public void addInterceptors(@NonNull InterceptorRegistry registry) {
        registry.addInterceptor(new JwtInterceptor(jwtUtil, jwtProperties.getHeader(), WHITELIST))
                .addPathPatterns("/**").excludePathPatterns(WHITELIST);
    }
}
