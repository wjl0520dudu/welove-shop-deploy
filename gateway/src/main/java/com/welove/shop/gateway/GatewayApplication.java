package com.welove.shop.gateway;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;

/**
 * 网关启动类。
 * <p>
 * 职责:显式路由(6 个下游服务)、CORS、Sentinel 限流(骨架)。
 * 不承担:业务逻辑。鉴权待所有微服务业务全完后统一升级到分层鉴权。
 */
@EnableDiscoveryClient
@SpringBootApplication
public class GatewayApplication {

    public static void main(String[] args) {
        SpringApplication.run(GatewayApplication.class, args);
    }

}
