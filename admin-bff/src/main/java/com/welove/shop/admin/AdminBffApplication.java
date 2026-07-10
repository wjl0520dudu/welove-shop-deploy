package com.welove.shop.admin;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.openfeign.EnableFeignClients;

/**
 * admin-bff 启动类。
 * <p>
 * 职责:管理端接口聚合 + 鉴权收口 + Dashboard(4 大 count)。
 * 自身仅存 admin 账号表,业务数据全部通过 Feign 调 user/product/trade/chat。
 */
@EnableDiscoveryClient
@EnableFeignClients
@SpringBootApplication
@MapperScan("com.welove.shop.admin.mapper")
public class AdminBffApplication {

    public static void main(String[] args) {
        SpringApplication.run(AdminBffApplication.class, args);
    }

}
