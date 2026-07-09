/**
 * common-security:通用安全模块根包。
 * <p>
 * 子包组织:
 * <ul>
 *   <li>{@code config}      — JwtProperties + CommonSecurityAutoConfiguration(JwtUtil + PasswordEncoder Bean)</li>
 *   <li>{@code jwt}         — JwtUtil(签发/解析/校验/去前缀)</li>
 *   <li>{@code context}     — UserContext(ThreadLocal 存 UserPrincipal)</li>
 *   <li>{@code interceptor} — JwtInterceptor(HandlerInterceptor,白名单 + Bearer 解析)</li>
 * </ul>
 * 各服务自己写 WebMvcConfigurer 决定拦截路径与白名单,common 不代管拦截器注册。
 */
package com.welove.shop.common.security;
