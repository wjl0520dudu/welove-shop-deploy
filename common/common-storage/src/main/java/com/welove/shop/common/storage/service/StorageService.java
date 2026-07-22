package com.welove.shop.common.storage.service;

import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;

/**
 * 对象存储抽象接口。
 * <p>
 * 业务侧只需要面向此接口编程,不关心底层是阿里云 OSS / 腾讯云 COS / AWS S3 / 本地磁盘。
 * 自动装配会根据配置注入不同的实现。
 *
 * <p>对象 key 格式约定:{@code <keyPrefix>/yyyy-MM-dd/<uuid>_<原文件名>},不含 domain。
 * 完整 URL 走 {@link #getUrl(String)} 拼接。</p>
 */
public interface StorageService {

    /**
     * 上传流式内容,返回对象 key。
     *
     * @param key         业务侧指定的完整 key(若包含 keyPrefix 前缀,需自行拼接)
     * @param content     输入流(由调用方负责关闭)
     * @param size        内容字节数(传 -1 表示未知,实现侧按流式处理)
     * @param contentType MIME 类型,可为 null
     * @return 对象 key
     */
    String put(String key, InputStream content, long size, String contentType);

    /**
     * 上传 {@link MultipartFile} 便捷方法:自动生成 key 并写入。
     *
     * @return 对象 key
     */
    default String put(MultipartFile file) throws IOException {
        if (file == null || file.isEmpty()) {
            throw new IllegalArgumentException("上传文件为空");
        }
        String original = file.getOriginalFilename() == null ? "file" : file.getOriginalFilename();
        try (InputStream in = file.getInputStream()) {
            return put(generateKey(original), in, file.getSize(), file.getContentType());
        }
    }

    /**
     * 根据对象 key 拼出可访问的完整 URL(走 {@code cloud.storage.domain} 配置)。
     * <p>不允许任何业务代码绕过此方法硬编码 *.aliyuncs.com / CDN 主机。</p>
     */
    String getUrl(String key);

    /** 删除一个对象。idempotent:对象不存在不抛异常。 */
    void delete(String key);

    /** 判断对象是否存在。 */
    boolean exists(String key);

    /**
     * 生成一个 key:&lt;prefix&gt;/yyyy-MM-dd/&lt;uuid&gt;_&lt;原始文件名&gt;。
     * 子类可覆盖以实现不同命名规则。
     */
    default String generateKey(String originalFilename) {
        String prefix = keyPrefix();
        String date = java.time.LocalDate.now().toString();
        String uuid = java.util.UUID.randomUUID().toString().replace("-", "");
        String safeName = originalFilename == null ? "file" : originalFilename;
        // 防路径穿越:只保留文件名部分
        int slash = Math.max(safeName.lastIndexOf('/'), safeName.lastIndexOf('\\'));
        if (slash >= 0) {
            safeName = safeName.substring(slash + 1);
        }
        StringBuilder sb = new StringBuilder();
        if (prefix != null && !prefix.isEmpty()) {
            sb.append(prefix);
            if (!prefix.endsWith("/")) sb.append('/');
        }
        sb.append(date).append('/').append(uuid).append('_').append(safeName);
        return sb.toString();
    }

    /** 当前生效的 key prefix(由实现从 properties 取)。 */
    String keyPrefix();
}
