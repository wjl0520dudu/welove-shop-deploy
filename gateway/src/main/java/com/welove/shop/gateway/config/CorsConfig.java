package com.welove.shop.gateway.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.reactive.CorsWebFilter;
import org.springframework.web.cors.reactive.UrlBasedCorsConfigurationSource;

import java.util.List;

/**
 * 全局 CORS 配置(WebFlux 响应式风格,与 Spring MVC 不同)。
 * <p>
 * 骨架期允许所有本地开发端口访问。上线前收窄到具体域名。
 * <p>
 * 覆盖的 Header:
 * <ul>
 *   <li>{@code Authorization} — 前端登录后携带 Bearer token</li>
 *   <li>{@code Content-Type} — application/json</li>
 *   <li>{@code X-Requested-With} — Axios/AJAX 常见</li>
 * </ul>
 */
@Configuration
public class CorsConfig {

    @Bean
    public CorsWebFilter corsWebFilter() {
        CorsConfiguration cfg = new CorsConfiguration();
        // 骨架期宽松:allowedOriginPatterns 允许所有 origin 且能带 credentials
        cfg.setAllowedOriginPatterns(List.of("*"));
        cfg.setAllowedMethods(List.of(
                HttpMethod.GET.name(), HttpMethod.POST.name(), HttpMethod.PUT.name(),
                HttpMethod.DELETE.name(), HttpMethod.OPTIONS.name(), HttpMethod.PATCH.name()));
        cfg.setAllowedHeaders(List.of("*"));
        cfg.setAllowCredentials(true);
        cfg.setMaxAge(3600L);                    // 预检缓存 1h

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", cfg);
        return new CorsWebFilter(source);
    }
}
