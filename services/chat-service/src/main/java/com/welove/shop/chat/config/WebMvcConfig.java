package com.welove.shop.chat.config;

import com.welove.shop.common.security.config.JwtProperties;
import com.welove.shop.common.security.interceptor.JwtInterceptor;
import com.welove.shop.common.security.jwt.JwtUtil;
import org.springframework.context.annotation.Configuration;
import org.springframework.lang.NonNull;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.List;

@Configuration
public class WebMvcConfig implements WebMvcConfigurer {
    private final JwtUtil jwtUtil;
    private final JwtProperties jwtProperties;

    private static final List<String> WHITELIST = List.of(
            "/api/notice/latest",
            "/api/internal/**",    // 内部统计接口(admin-bff Dashboard Feign 调)
            "/actuator/**",
            "/error"
    );

    public WebMvcConfig(JwtUtil jwtUtil, JwtProperties jwtProperties) {
        this.jwtUtil = jwtUtil; this.jwtProperties = jwtProperties;
    }

    @Override
    public void addInterceptors(@NonNull InterceptorRegistry registry) {
        registry.addInterceptor(new JwtInterceptor(jwtUtil, jwtProperties.getHeader(), WHITELIST))
                .addPathPatterns("/api/**").excludePathPatterns(WHITELIST);
    }
}
