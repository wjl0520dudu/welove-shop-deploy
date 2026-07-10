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
     * 免鉴权路径 —— 商品浏览类 GET 接口全匿名。
     * <p>
     * 提交评价 POST /api/product/{id}/reviews 不在白名单,拦截器解析 token 后由
     * ProductResourceController.submitReview 校验 UserContext。
     * 评价列表 GET 走 /api/product/{id} 详情聚合,不单独暴露。
     * 推荐日志相关 /api/recommend-log/** 全部需登录,不在白名单。
     */
    private static final List<String> WHITELIST = List.of(
            "/api/category/**",
            "/api/product/list",
            "/api/product/search",
            "/api/product/hot",
            "/api/product/*",              // /api/product/{id} 详情聚合(含 reviews)
            "/api/product/*/skus",
            "/api/product/*/images",
            "/api/product/*/faqs",
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
