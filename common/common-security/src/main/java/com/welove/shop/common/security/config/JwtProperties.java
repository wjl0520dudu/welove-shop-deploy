package com.welove.shop.common.security.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * JWT 配置属性。
 * <p>
 * yml 示例:
 * <pre>
 * jwt:
 *   secret: xxxxxxxx  # 32 字节以上 base64/明文,HS256 要求
 *   expiration: 3600000            # access token 1 小时(ms)
 *   refresh-expiration: 86400000   # refresh token 24 小时(ms)
 *   header: Authorization          # 从哪个 Header 读 token
 *   prefix: "Bearer "              # 前缀
 * </pre>
 */
@ConfigurationProperties(prefix = "jwt")
public class JwtProperties {

    /** HS256 密钥,长度需 >= 32 字节。 */
    private String secret;

    /** access token 有效期(毫秒)。默认 1 小时。 */
    private long expiration = 3600_000L;

    /** refresh token 有效期(毫秒)。默认 24 小时。 */
    private long refreshExpiration = 86400_000L;

    /** 从哪个 HTTP Header 读取 token。 */
    private String header = "Authorization";

    /** Header 值前缀,如 "Bearer "(注意末尾空格)。 */
    private String prefix = "Bearer ";

    public String getSecret() {
        return secret;
    }

    public void setSecret(String secret) {
        this.secret = secret;
    }

    public long getExpiration() {
        return expiration;
    }

    public void setExpiration(long expiration) {
        this.expiration = expiration;
    }

    public long getRefreshExpiration() {
        return refreshExpiration;
    }

    public void setRefreshExpiration(long refreshExpiration) {
        this.refreshExpiration = refreshExpiration;
    }

    public String getHeader() {
        return header;
    }

    public void setHeader(String header) {
        this.header = header;
    }

    public String getPrefix() {
        return prefix;
    }

    public void setPrefix(String prefix) {
        this.prefix = prefix;
    }
}
