/**
 * common-web:通用 Web 模块根包。
 * <p>
 * 子包组织:
 * <ul>
 *   <li>{@code exception} — GlobalExceptionHandler(全局异常 → Result 统一转换)</li>
 *   <li>{@code config}    — CommonWebAutoConfiguration(Spring Boot 3 自动装配入口)</li>
 * </ul>
 * 通过 {@code META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports}
 * 让子服务只要引入 common-web 依赖,就自动挂上全局异常处理器,零 import。
 */
package com.welove.shop.common.web;
