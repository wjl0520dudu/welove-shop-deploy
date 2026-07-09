package com.welove.shop.admin;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.openfeign.EnableFeignClients;

/**
 * admin-bff 启动类。
 * <p>
 * 职责:管理端接口聚合、鉴权收口。自身不持有业务数据,全部通过 Feign 走 user/product/trade/chat。
 */
@EnableDiscoveryClient
@EnableFeignClients
@SpringBootApplication
public class AdminBffApplication {

    public static void main(String[] args) {
        SpringApplication.run(AdminBffApplication.class, args);
    }

}
