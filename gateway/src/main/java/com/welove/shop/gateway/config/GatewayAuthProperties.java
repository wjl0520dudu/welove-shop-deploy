package com.welove.shop.gateway.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.ArrayList;
import java.util.List;

/**
 * gateway 鉴权白名单配置。
 * <p>
 * yml 示例:
 * <pre>
 * gateway-auth:
 *   whitelist:
 *     - /user/api/auth/login
 *     - /product/api/product/list
 * </pre>
 * 命中白名单的请求不做 JWT 校验,直接放行到下游。
 */
@ConfigurationProperties(prefix = "gateway-auth")
public class GatewayAuthProperties {

    /** 免鉴权路径(Ant 通配符,gateway 侧带 /{service} 前缀)。 */
    private List<String> whitelist = new ArrayList<>();

    public List<String> getWhitelist() {
        return whitelist;
    }

    public void setWhitelist(List<String> whitelist) {
        this.whitelist = whitelist;
    }
}
