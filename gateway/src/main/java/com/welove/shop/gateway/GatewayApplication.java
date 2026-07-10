package com.welove.shop.gateway;

import com.welove.shop.gateway.config.GatewayAuthProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;

/**
 * 网关启动类。
 * <p>
 * 职责:统一入口、显式路由(6 个下游服务)、分层鉴权(JWT GlobalFilter)、CORS、Sentinel 限流(骨架)。
 * 不承担:任何业务逻辑,下游服务侧仍保留 JwtInterceptor 做兜底(零信任双重鉴权)。
 */
@EnableDiscoveryClient
@EnableConfigurationProperties(GatewayAuthProperties.class)
@SpringBootApplication
public class GatewayApplication {

    public static void main(String[] args) {
        SpringApplication.run(GatewayApplication.class, args);
    }

}
