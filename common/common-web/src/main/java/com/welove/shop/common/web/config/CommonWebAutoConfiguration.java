package com.welove.shop.common.web.config;

import com.welove.shop.common.web.exception.GlobalExceptionHandler;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.context.annotation.Bean;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * common-web 自动装配入口。
 * <p>
 * 服务只要 {@code <dependency>} 引 common-web,Spring Boot 就会自动把
 * {@link GlobalExceptionHandler} 装进 IoC 容器,不用在启动类上加 {@code @Import}。
 * <p>
 * 服务如需替换,自己声明同名 bean 即可(@ConditionalOnMissingBean 保证不会重复注册)。
 */
@AutoConfiguration
@ConditionalOnClass(RestControllerAdvice.class)
public class CommonWebAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean
    GlobalExceptionHandler globalExceptionHandler() {
        return new GlobalExceptionHandler();
    }
}
