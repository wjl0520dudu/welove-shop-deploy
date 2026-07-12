package com.welove.shop.common.storage.service;

import com.aliyun.oss.OSS;
import com.aliyun.oss.OSSClientBuilder;
import com.aliyun.oss.model.OSSObject;
import com.aliyun.oss.model.ObjectMetadata;
import com.welove.shop.common.storage.config.CloudStorageProperties;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

import java.io.InputStream;
import java.util.Date;

/**
 * 阿里云 OSS 实现。
 * <p>前提:Bucket 已设置为"公共读"模式 — 直接拼 {@code https://<bucket>.<endpoint>/<key>}
 * 即可匿名访问,无需预签名 URL。</p>
 *
 * <p>Bean 装配条件:由 {@code CommonStorageAutoConfiguration} 上的
 * {@code @ConditionalOnProperty(prefix="cloud.storage", name="access-key")} 控制,
 * 凭证完整时本实现才生效,否则降级到 {@link LocalDiskStorageService}。</p>
 */
@Slf4j
@RequiredArgsConstructor
public class AliyunOssStorageService implements StorageService {

    private final CloudStorageProperties props;
    private volatile OSS ossClient;

    @PostConstruct
    void init() {
        // endpoint 不带协议头,SDK 接受带或不带两种形式,这里统一为 "https://<endpoint>"
        String endpoint = props.getEndpoint();
        String fullEndpoint = endpoint.startsWith("http://") || endpoint.startsWith("https://")
                ? endpoint
                : "https://" + endpoint;
        this.ossClient = new OSSClientBuilder()
                .build(fullEndpoint, props.getAccessKey(), props.getSecretKey());
        log.info("[AliyunOssStorageService] 初始化完成 bucket={} endpoint={}", props.getBucket(), fullEndpoint);
    }

    @PreDestroy
    void destroy() {
        if (ossClient != null) {
            try {
                ossClient.shutdown();
            } catch (Exception e) {
                log.warn("[AliyunOssStorageService] shutdown 异常: {}", e.getMessage());
            }
        }
    }

    @Override
    public String put(String key, InputStream content, long size, String contentType) {
        ObjectMetadata meta = new ObjectMetadata();
        if (size >= 0) meta.setContentLength(size);
        if (contentType != null && !contentType.isBlank()) meta.setContentType(contentType);
        // 公共读 Bucket 不需要设置 ACL;若 Bucket 不是公共读,这里会返回 403
        ossClient.putObject(props.getBucket(), key, content, meta);
        return key;
    }

    @Override
    public String getUrl(String key) {
        String domain = props.getDomain();
        if (domain != null && !domain.isBlank()) {
            return trimTrailingSlash(domain) + "/" + key;
        }
        // 默认走 OSS 公共读域名
        return "https://" + props.getBucket() + "." + props.getEndpoint() + "/" + key;
    }

    @Override
    public void delete(String key) {
        try {
            ossClient.deleteObject(props.getBucket(), key);
        } catch (Exception e) {
            log.warn("[AliyunOssStorageService] delete 失败 key={} err={}", key, e.getMessage());
        }
    }

    @Override
    public boolean exists(String key) {
        try {
            return ossClient.doesObjectExist(props.getBucket(), key);
        } catch (Exception e) {
            log.warn("[AliyunOssStorageService] exists 失败 key={} err={}", key, e.getMessage());
            return false;
        }
    }

    @Override
    public String keyPrefix() {
        return props.getKeyPrefix();
    }

    private static String trimTrailingSlash(String s) {
        return s.endsWith("/") ? s.substring(0, s.length() - 1) : s;
    }

    /**
     * 便捷方法:生成一段时间有效的预签名 URL(公共读 Bucket 一般用不到,留作后续切换私有模式时用)。
     */
    public String generatePresignedUrl(String key, Date expiration) {
        return ossClient.generatePresignedUrl(props.getBucket(), key, expiration).toString();
    }

    /** 暴露 OSSObject 给需要直读流的场景(用完必须 close)。 */
    public OSSObject getObject(String key) {
        return ossClient.getObject(props.getBucket(), key);
    }
}
