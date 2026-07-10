package com.welove.shop.trade;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.openfeign.EnableFeignClients;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * trade-service 启动类。
 * <p>
 * 职责:购物车、订单、订单项、支付/发货状态流转、订单超时定时任务。
 */
@EnableDiscoveryClient
@EnableFeignClients
@EnableScheduling
@SpringBootApplication
@MapperScan("com.welove.shop.trade.mapper")
public class TradeServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(TradeServiceApplication.class, args);
    }

}
