package com.welove.shop.common.storage.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 云存储配置属性。
 * <p>
 * yml 示例(以阿里云 OSS 公共读模式为例):
 * <pre>
 * cloud:
 *   storage:
 *     access-key: xxxxx          # AccessKeyId
 *     secret-key: xxxxx          # AccessKeySecret
 *     bucket: liangwenjun        # Bucket 名
 *     endpoint: oss-cn-hangzhou.aliyuncs.com   # 地域 Endpoint
 *     # 公共可访问的基础 URL(留空则默认按 https://{bucket}.{endpoint} 拼接)
 *     domain:                    # 配 CDN 时填 CDN 主机,如 https://cdn.example.com
 *     # 对象 key 命名前缀(便于在 Bucket 内按服务归类)
 *     key-prefix: chat/          # 留空则用空字符串
 * </pre>
 * <p>
 * 凭证(access-key / secret-key) 留空时,自动装配会降级到 {@code LocalDiskStorageService}。
 *
 * <p>设计原则:保持中性命名("云存储"),便于后续切换到其他对象存储供应商。</p>
 */
@ConfigurationProperties(prefix = "cloud.storage")
public class CloudStorageProperties {

    /** AccessKeyId(空 → 降级为本地磁盘存储)。 */
    private String accessKey;

    /** AccessKeySecret。 */
    private String secretKey;

    /** Bucket 名。 */
    private String bucket;

    /** 地域 Endpoint(不含协议头),如 oss-cn-hangzhou.aliyuncs.com。 */
    private String endpoint;

    /**
     * 公共可访问的基础 URL(不含末尾 /)。<br>
     * 留空时,默认按 {@code https://{bucket}.{endpoint}} 拼接;<br>
     * 配 CDN 时填 CDN 主机,如 {@code https://cdn.example.com}。
     */
    private String domain;

    /** 对象 key 命名前缀(不含末尾 /),如 chat/。 */
    private String keyPrefix = "";

    public String getAccessKey() { return accessKey; }
    public void setAccessKey(String accessKey) { this.accessKey = accessKey; }

    public String getSecretKey() { return secretKey; }
    public void setSecretKey(String secretKey) { this.secretKey = secretKey; }

    public String getBucket() { return bucket; }
    public void setBucket(String bucket) { this.bucket = bucket; }

    public String getEndpoint() { return endpoint; }
    public void setEndpoint(String endpoint) { this.endpoint = endpoint; }

    public String getDomain() { return domain; }
    public void setDomain(String domain) { this.domain = domain; }

    public String getKeyPrefix() { return keyPrefix; }
    public void setKeyPrefix(String keyPrefix) { this.keyPrefix = keyPrefix; }

    /** 凭证是否完整(任一为空都视为未配置)。 */
    public boolean isCredentialsComplete() {
        return accessKey != null && !accessKey.isBlank()
                && secretKey != null && !secretKey.isBlank()
                && bucket != null && !bucket.isBlank()
                && endpoint != null && !endpoint.isBlank();
    }
}
