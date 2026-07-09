package com.welove.shop.common.security.jwt;

import com.welove.shop.common.security.config.JwtProperties;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jws;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;

/**
 * JWT 工具:签发/解析/校验 token。
 * <p>
 * 基于 jjwt 0.12.x API,HS256 对称签名。密钥、有效期从 {@link JwtProperties} 读。
 * <p>
 * Token 载荷约定:
 * <ul>
 *   <li>{@code sub}      — userId(String)</li>
 *   <li>{@code phone}    — 手机号(可选)</li>
 *   <li>{@code username} — 用户名(可选)</li>
 *   <li>{@code role}     — 角色标识(可选,如 USER / ADMIN)</li>
 * </ul>
 */
public class JwtUtil {

    private static final Logger log = LoggerFactory.getLogger(JwtUtil.class);

    private final JwtProperties props;
    private final SecretKey key;

    public JwtUtil(JwtProperties props) {
        this.props = props;
        if (props.getSecret() == null || props.getSecret().getBytes(StandardCharsets.UTF_8).length < 32) {
            throw new IllegalStateException("jwt.secret 长度不足 32 字节,HS256 需要至少 32 字节密钥");
        }
        this.key = Keys.hmacShaKeyFor(props.getSecret().getBytes(StandardCharsets.UTF_8));
    }

    // ---------- 签发 ----------

    /**
     * 签发 access token。
     *
     * @param userId  用户 ID,写入 subject
     * @param claims  额外声明(phone/username/role 等),可为 null
     */
    public String generateToken(Long userId, Map<String, Object> claims) {
        Date now = new Date();
        Date expiry = new Date(now.getTime() + props.getExpiration());
        return Jwts.builder()
                .subject(String.valueOf(userId))
                .claims(claims == null ? new HashMap<>() : claims)
                .issuedAt(now)
                .expiration(expiry)
                .signWith(key)
                .compact();
    }

    /** 签发 refresh token,只带 sub,不带业务 claims。 */
    public String generateRefreshToken(Long userId) {
        Date now = new Date();
        Date expiry = new Date(now.getTime() + props.getRefreshExpiration());
        return Jwts.builder()
                .subject(String.valueOf(userId))
                .issuedAt(now)
                .expiration(expiry)
                .signWith(key)
                .compact();
    }

    // ---------- 解析 ----------

    /** 解析 token 并返回 Claims,失败抛 {@link JwtException}。 */
    public Claims parse(String token) {
        Jws<Claims> jws = Jwts.parser()
                .verifyWith(key)
                .build()
                .parseSignedClaims(token);
        return jws.getPayload();
    }

    /** 只校验有效性,不需要 payload 时用。 */
    public boolean validate(String token) {
        try {
            parse(token);
            return true;
        } catch (JwtException | IllegalArgumentException e) {
            log.debug("jwt validate failed: {}", e.getMessage());
            return false;
        }
    }

    /** 从 token 提取 userId。 */
    public Long getUserId(String token) {
        return Long.parseLong(parse(token).getSubject());
    }

    // ---------- 辅助:从 Header 值提取 token ----------

    /** 输入形如 "Bearer xxxxxxx" 的 Header 值,返回去前缀后的 token,失败返回 null。 */
    public String stripPrefix(String headerValue) {
        if (headerValue == null || headerValue.isEmpty()) {
            return null;
        }
        String prefix = props.getPrefix();
        if (prefix != null && !prefix.isEmpty() && headerValue.startsWith(prefix)) {
            return headerValue.substring(prefix.length());
        }
        // 兼容不带前缀直接传 token 的情况
        return headerValue;
    }
}
