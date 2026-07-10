package com.welove.shop.admin.config;

import com.welove.shop.admin.interceptor.AdminInterceptor;
import com.welove.shop.common.security.config.JwtProperties;
import com.welove.shop.common.security.jwt.JwtUtil;
import org.springframework.context.annotation.Configuration;
import org.springframework.lang.NonNull;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.List;

/**
 * admin-bff Web 配置:注册 AdminInterceptor + 白名单。
 * <p>
 * 只有 role=ADMIN 的 token 才能访问 /api/admin/**。
 */
@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    private final JwtUtil jwtUtil;
    private final JwtProperties jwtProperties;

    /** 免鉴权路径。 */
    private static final List<String> WHITELIST = List.of(
            "/api/admin/login",
            "/actuator/**",
            "/error"
    );

    public WebMvcConfig(JwtUtil jwtUtil, JwtProperties jwtProperties) {
        this.jwtUtil = jwtUtil;
        this.jwtProperties = jwtProperties;
    }

    @Override
    public void addInterceptors(@NonNull InterceptorRegistry registry) {
        registry.addInterceptor(new AdminInterceptor(jwtUtil, jwtProperties.getHeader(), WHITELIST))
                .addPathPatterns("/api/**")
                .excludePathPatterns(WHITELIST);
    }
}
