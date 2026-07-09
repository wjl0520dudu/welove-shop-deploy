/**
 * common-db:通用数据层根包。
 * <p>
 * 子包组织:
 * <ul>
 *   <li>{@code entity}  — BaseEntity(create/update_time 基类)</li>
 *   <li>{@code handler} — AutoFillMetaObjectHandler(时间字段自动填充)</li>
 *   <li>{@code config}  — CommonDbAutoConfiguration(分页插件 + 自动填充装配入口)</li>
 * </ul>
 * 子服务引入本模块后,分页与时间自动填充开箱即用。
 * Mapper 扫描由各服务自己在启动类上声明,common 不代管。
 */
package com.welove.shop.common.db;
