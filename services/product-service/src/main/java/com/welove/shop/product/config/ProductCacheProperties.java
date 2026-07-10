package com.welove.shop.product.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * product-service Redis 缓存 TTL 配置(从 product-service.cache.* 读取)。
 *
 * <pre>
 * product-service:
 *   cache:
 *     product-detail-ttl: 300     # 秒,0 表示不缓存
 *     category-list-ttl: 600
 *     hot-products-ttl: 60
 * </pre>
 */
@ConfigurationProperties(prefix = "product-service.cache")
public class ProductCacheProperties {

    /** 商品详情缓存 TTL(秒)。 */
    private long productDetailTtl = 300;

    /** 分类列表缓存 TTL(秒)。 */
    private long categoryListTtl = 600;

    /** 热门商品缓存 TTL(秒)。 */
    private long hotProductsTtl = 60;

    public long getProductDetailTtl() {
        return productDetailTtl;
    }

    public void setProductDetailTtl(long productDetailTtl) {
        this.productDetailTtl = productDetailTtl;
    }

    public long getCategoryListTtl() {
        return categoryListTtl;
    }

    public void setCategoryListTtl(long categoryListTtl) {
        this.categoryListTtl = categoryListTtl;
    }

    public long getHotProductsTtl() {
        return hotProductsTtl;
    }

    public void setHotProductsTtl(long hotProductsTtl) {
        this.hotProductsTtl = hotProductsTtl;
    }
}
