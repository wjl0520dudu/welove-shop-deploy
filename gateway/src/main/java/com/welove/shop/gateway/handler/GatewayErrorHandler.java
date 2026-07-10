package com.welove.shop.gateway.handler;

import com.welove.shop.common.core.result.Result;
import com.welove.shop.common.core.util.JsonUtil;
import org.springframework.boot.web.reactive.error.ErrorWebExceptionHandler;
import org.springframework.core.annotation.Order;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;

/**
 * Gateway 全局异常处理(WebFlux 风格)。
 * <p>
 * 将所有未捕获异常转为统一 Result JSON,避免暴露堆栈。
 */
@Component
@Order(-2)
public class GatewayErrorHandler implements ErrorWebExceptionHandler {

    @Override
    public Mono<Void> handle(ServerWebExchange exchange, Throwable ex) {
        Result<Void> body = Result.fail(10500, "网关内部错误");
        String json = JsonUtil.toJson(body);
        byte[] bytes = json.getBytes(StandardCharsets.UTF_8);
        exchange.getResponse().setStatusCode(HttpStatus.OK);
        exchange.getResponse().getHeaders().setContentType(MediaType.APPLICATION_JSON);
        DataBuffer buffer = exchange.getResponse().bufferFactory().wrap(bytes);
        return exchange.getResponse().writeWith(Mono.just(buffer));
    }
}
