package com.welove.shop.common.storage.config;

import com.aliyun.oss.OSS;
import com.welove.shop.common.storage.service.AliyunOssStorageService;
import com.welove.shop.common.storage.service.LocalDiskStorageService;
import com.welove.shop.common.storage.service.StorageService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnExpression;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;

/**
 * common-storage 自动装配入口。
 * <p>
 * 装配策略:
 * <ul>
 *   <li>当 {@code cloud.storage.access-key} 非空时,装配 {@link AliyunOssStorageService}</li>
 *   <li>否则,装配 {@link LocalDiskStorageService}(骨架期降级)</li>
 * </ul>
 * <p>两种实现对外都是 {@link StorageService} 接口,业务侧无感切换。</p>
 */
@AutoConfiguration
@EnableConfigurationProperties(CloudStorageProperties.class)
public class CommonStorageAutoConfiguration {

    /** 本地磁盘存储的写入目录(默认 ./uploads)。 */
    @Value("${upload.dir:./uploads}")
    private String uploadDir;

    /**
     * 阿里云 OSS 实现 — 凭证完整时生效。
     * <p>{@code matchIfMissing=false} 保证不配置时不会误激活,默认走 LocalDisk。</p>
     */
    @Bean
    @ConditionalOnMissingBean(StorageService.class)
    @ConditionalOnClass(OSS.class)
    @ConditionalOnExpression(
            "T(org.springframework.util.StringUtils).hasText('${cloud.storage.access-key:}')"
                    + " && T(org.springframework.util.StringUtils).hasText('${cloud.storage.secret-key:}')"
                    + " && T(org.springframework.util.StringUtils).hasText('${cloud.storage.bucket:}')"
                    + " && T(org.springframework.util.StringUtils).hasText('${cloud.storage.endpoint:}')")
    public AliyunOssStorageService aliyunOssStorageService(CloudStorageProperties props) {
        return new AliyunOssStorageService(props);
    }

    /**
     * 本地磁盘降级实现 — 凭证缺失时生效。
     * <p>注意:用 {@code havingValue} 而不是 {@code matchIfMissing} — 缺省值视为"空字符串",与缺失等价。</p>
     */
    @Bean
    @ConditionalOnMissingBean(StorageService.class)
    public StorageService localDiskStorageService(CloudStorageProperties props) {
        return new LocalDiskStorageService(uploadDir, props.getDomain(), props.getKeyPrefix());
    }
}
