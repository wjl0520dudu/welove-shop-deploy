package com.welove.shop.common.db.config;

import com.baomidou.mybatisplus.annotation.DbType;
import com.baomidou.mybatisplus.core.handlers.MetaObjectHandler;
import com.baomidou.mybatisplus.extension.plugins.MybatisPlusInterceptor;
import com.baomidou.mybatisplus.extension.plugins.inner.PaginationInnerInterceptor;
import com.welove.shop.common.db.handler.AutoFillMetaObjectHandler;
import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.context.annotation.Bean;

/**
 * common-db 自动装配入口。
 * <p>
 * 提供:
 * <ul>
 *   <li>{@link MybatisPlusInterceptor} — PG 分页插件</li>
 *   <li>{@link AutoFillMetaObjectHandler} — create/update_time 自动填充</li>
 * </ul>
 * 服务只要 {@code <dependency>} 引 common-db,以上两项 Bean 就自动装配好,不用在启动类加 {@code @Import}。
 * <p>
 * <b>Mapper 扫描不在此配置</b>:各服务自己在启动类上加 {@code @MapperScan("com.welove.shop.xxx.mapper")}
 * ,或写在 pom 层用 {@link MapperScan}。common 不应假设子服务的 mapper 包路径。
 */
@AutoConfiguration
@ConditionalOnClass(MybatisPlusInterceptor.class)
public class CommonDbAutoConfiguration {

    /** 分页插件。DbType 用 POSTGRE_SQL,方言使用 PG 的 LIMIT/OFFSET。 */
    @Bean
    @ConditionalOnMissingBean
    MybatisPlusInterceptor mybatisPlusInterceptor() {
        MybatisPlusInterceptor interceptor = new MybatisPlusInterceptor();
        interceptor.addInnerInterceptor(new PaginationInnerInterceptor(DbType.POSTGRE_SQL));
        return interceptor;
    }

    /** create_time / update_time 自动填充。 */
    @Bean
    @ConditionalOnMissingBean
    MetaObjectHandler metaObjectHandler() {
        return new AutoFillMetaObjectHandler();
    }
}
