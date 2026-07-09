/**
 * common-core:通用核心模块根包。
 * <p>
 * 子包组织:
 * <ul>
 *   <li>{@code exception} — ErrorCode 枚举 + BizException</li>
 *   <li>{@code result}    — Result 统一响应体 + PageResult 分页封装</li>
 *   <li>{@code util}      — JsonUtil / DateUtil 基础工具类(hutool 未覆盖或需自定义的场景)</li>
 * </ul>
 * 本模块不引入 web/db/security 依赖,任何服务模块都可以放心引用。
 */
package com.welove.shop.common.core;
