package com.welove.shop.product.config;

import com.welove.shop.common.security.config.JwtProperties;
import com.welove.shop.common.security.interceptor.JwtInterceptor;
import com.welove.shop.common.security.jwt.JwtUtil;
import org.springframework.context.annotation.Configuration;
import org.springframework.lang.NonNull;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.List;

/**
 * product-service Web 配置:注册 JWT 拦截器 + 白名单。
 * <p>
 * 商品浏览类接口全匿名(list/search/hot/详情/skus/images/faqs/reviews GET),
 * 提交评价和推荐日志相关需登录。
 */
@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    private final JwtUtil jwtUtil;
    private final JwtProperties jwtProperties;

    /**
     * 免鉴权路径 —— 商品浏览类 GET 接口全匿名(网关 StripPrefix=2 后收到的路径,无 /api 前缀)。
     * <p>
     * 提交评价 POST /product/{id}/reviews 不在白名单,拦截器解析 token 后由
     * ProductResourceController.submitReview 校验 UserContext。
     */
    private static final List<String> WHITELIST = List.of(
            "/category/**",
            "/product/list",
            "/product/search",
            "/product/hot",
            "/product/batch",          // 内部 Feign 批量查商品(骨架期免登录)
            "/product/sku/batch",      // 内部 Feign 批量查 SKU(骨架期免登录)
            "/product/*",              // /product/{id} 详情聚合(含 reviews)
            "/product/*/skus",
            "/product/*/images",
            "/product/*/faqs",
            "/internal/**",            // 内部统计接口(admin-bff Dashboard Feign 调)
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
                .addPathPatterns("/**")
                .excludePathPatterns(WHITELIST);
    }
}
