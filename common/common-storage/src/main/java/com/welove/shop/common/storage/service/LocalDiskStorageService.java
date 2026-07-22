package com.welove.shop.common.storage.service;

import lombok.extern.slf4j.Slf4j;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;

/**
 * 本地磁盘存储 — 骨架期降级实现。
 * <p>凭证未配置时由 {@code CommonStorageAutoConfiguration} 自动装配为 {@link StorageService} 的实现。
 * 写入 {@code upload.dir} 目录,getUrl 返回一个占位的本地 HTTP 路径。</p>
 *
 * <p><b>注意</b>:这不是生产实现,仅用于开发/演示场景,容器化部署时不要用它。</p>
 */
@Slf4j
public class LocalDiskStorageService implements StorageService {

    private final Path baseDir;
    private final String publicDomain;
    private final String keyPrefix;

    public LocalDiskStorageService(String uploadDir, String publicDomain, String keyPrefix) {
        this.baseDir = Paths.get(uploadDir == null || uploadDir.isBlank() ? "./uploads" : uploadDir);
        this.publicDomain = publicDomain == null || publicDomain.isBlank()
                ? "http://localhost:8888"
                : publicDomain;
        this.keyPrefix = keyPrefix == null ? "" : keyPrefix;
        try {
            Files.createDirectories(this.baseDir);
        } catch (IOException e) {
            throw new IllegalStateException("无法创建上传目录: " + this.baseDir, e);
        }
        log.info("[LocalDiskStorageService] 初始化 baseDir={} publicDomain={}", this.baseDir, this.publicDomain);
    }

    @Override
    public String put(String key, InputStream content, long size, String contentType) {
        Path dest = baseDir.resolve(key);
        try {
            Files.createDirectories(dest.getParent());
            Files.copy(content, dest, StandardCopyOption.REPLACE_EXISTING);
            return key;
        } catch (IOException e) {
            throw new RuntimeException("本地存储写入失败: " + dest, e);
        }
    }

    @Override
    public String getUrl(String key) {
        String base = publicDomain.endsWith("/") ? publicDomain.substring(0, publicDomain.length() - 1) : publicDomain;
        return base + "/uploads/" + key;
    }

    @Override
    public void delete(String key) {
        try {
            Files.deleteIfExists(baseDir.resolve(key));
        } catch (IOException e) {
            log.warn("[LocalDiskStorageService] delete 失败 key={} err={}", key, e.getMessage());
        }
    }

    @Override
    public boolean exists(String key) {
        return Files.exists(baseDir.resolve(key));
    }

    @Override
    public String keyPrefix() {
        return keyPrefix;
    }
}
