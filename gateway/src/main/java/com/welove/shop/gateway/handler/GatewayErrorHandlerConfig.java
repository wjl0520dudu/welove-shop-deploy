package com.welove.shop.gateway.handler;

import com.welove.shop.common.core.exception.BizException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.web.WebProperties;
import org.springframework.boot.autoconfigure.web.reactive.error.AbstractErrorWebExceptionHandler;
import org.springframework.boot.web.reactive.error.ErrorAttributes;
import org.springframework.cloud.gateway.support.NotFoundException;
import org.springframework.context.ApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerCodecConfigurer;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.server.RequestPredicates;
import org.springframework.web.reactive.function.server.RouterFunction;
import org.springframework.web.reactive.function.server.RouterFunctions;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

import java.util.HashMap;
import java.util.Map;

/**
 * gateway 全局错误处理。
 * <p>
 * WebFlux 环境下不能用 {@code @RestControllerAdvice}(那是 Spring MVC 的),
 * 需要自定义 {@link AbstractErrorWebExceptionHandler}。
 * <p>
 * 覆盖:
 * <ul>
 *   <li>{@link NotFoundException} — 下游服务未找到 / LB 无实例,返回 503</li>
 *   <li>{@link BizException} — 业务异常,按 code 返回</li>
 *   <li>其他 —— 500 系统错误</li>
 * </ul>
 * <p>
 * <b>注意:</b>{@link com.welove.shop.gateway.filter.JwtAuthGlobalFilter} 里的 401 已经在
 * filter 内部直接写响应体了,不走这里。这里只兜底其他异常。
 */
@Slf4j
@Configuration
public class GatewayErrorHandlerConfig {

    @Bean
    @Order(-2)                                   // 优先于默认的 DefaultErrorWebExceptionHandler
    public GatewayGlobalErrorHandler gatewayGlobalErrorHandler(
            ErrorAttributes errorAttributes, WebProperties.Resources resources,
            ApplicationContext applicationContext, ServerCodecConfigurer codecConfigurer) {
        GatewayGlobalErrorHandler handler = new GatewayGlobalErrorHandler(
                errorAttributes, resources, applicationContext);
        handler.setMessageWriters(codecConfigurer.getWriters());
        handler.setMessageReaders(codecConfigurer.getReaders());
        return handler;
    }

    @Bean
    public WebProperties.Resources resources() {
        return new WebProperties.Resources();
    }

    /** 具体实现类。 */
    public static class GatewayGlobalErrorHandler extends AbstractErrorWebExceptionHandler {

        public GatewayGlobalErrorHandler(ErrorAttributes errorAttributes, WebProperties.Resources resources,
                                        ApplicationContext applicationContext) {
            super(errorAttributes, resources, applicationContext);
        }

        @Override
        protected RouterFunction<ServerResponse> getRoutingFunction(ErrorAttributes errorAttributes) {
            return RouterFunctions.route(RequestPredicates.all(), this::renderError);
        }

        private Mono<ServerResponse> renderError(ServerRequest request) {
            Throwable ex = getError(request);
            HttpStatus status;
            int code;
            String message;

            if (ex instanceof NotFoundException) {
                status = HttpStatus.SERVICE_UNAVAILABLE;
                code = 10006;                    // ErrorCode.SERVICE_UNAVAILABLE
                message = "下游服务不可用: " + ex.getMessage();
                log.warn("[gateway] service unavailable: {}", ex.getMessage());
            } else if (ex instanceof BizException be) {
                status = HttpStatus.OK;
                code = be.getCode();
                message = be.getMessage();
            } else {
                status = HttpStatus.INTERNAL_SERVER_ERROR;
                code = 10500;                    // INTERNAL_ERROR
                message = "网关内部错误";
                log.error("[gateway] unhandled error: {} {}",
                        request.method(), request.path(), ex);
            }

            Map<String, Object> body = new HashMap<>();
            body.put("code", code);
            body.put("message", message);
            body.put("data", null);
            body.put("success", false);

            return ServerResponse.status(status)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(BodyInserters.fromValue(body));
        }
    }
}
