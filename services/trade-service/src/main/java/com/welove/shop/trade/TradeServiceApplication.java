package com.welove.shop.trade;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.openfeign.EnableFeignClients;

/**
 * trade-service 启动类。
 * <p>
 * 职责:购物车、订单、订单项、支付/发货状态机。
 */
@EnableDiscoveryClient
@EnableFeignClients
@SpringBootApplication
public class TradeServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(TradeServiceApplication.class, args);
    }

}
