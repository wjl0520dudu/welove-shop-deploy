package com.welove.shop.chat;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.openfeign.EnableFeignClients;

/**
 * chat-service 启动类。
 * <p>
 * 职责:AI 会话/消息/上下文管理、Agent 运行&步骤日志、公告推送,
 * 通过 HTTP 代理 Python 侧的 ai-service。
 */
@EnableDiscoveryClient
@EnableFeignClients
@SpringBootApplication
public class ChatServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(ChatServiceApplication.class, args);
    }

}
