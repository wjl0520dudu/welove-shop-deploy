package com.welove.shop.product.cache;

import com.welove.shop.product.config.ProductCacheProperties;
import com.welove.shop.product.entity.Category;
import com.welove.shop.product.entity.Product;
import com.welove.shop.product.vo.ProductDetailVO;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * product-service 缓存管理器。
 * <p>
 * 集中管理 3 类 key,便于命名规则统一 + 失效逻辑集中:
 * <ul>
 *   <li>{@code product:detail:{id}}      商品详情 VO(TTL 由 product-service.cache.product-detail-ttl 控)</li>
 *   <li>{@code product:category:list}    分类列表(TTL 由 product-service.cache.category-list-ttl 控)</li>
 *   <li>{@code product:hot:{limit}}      热门商品(TTL 由 product-service.cache.hot-products-ttl 控)</li>
 * </ul>
 * <p>
 * 失效策略:数据修改(商品/分类)后主动 evict,避免脏数据。
 */
@Component
@RequiredArgsConstructor
public class ProductCache {

    private static final Logger log = LoggerFactory.getLogger(ProductCache.class);

    /** 商品详情 key: product:detail:{id} */
    private static final String KEY_DETAIL = "product:detail:";

    /** 分类列表 key(固定) */
    private static final String KEY_CATEGORY_LIST = "product:category:list";

    /** 热门商品 key: product:hot:{limit} */
    private static final String KEY_HOT = "product:hot:";

    private final RedisTemplate<String, Object> redis;
    private final ProductCacheProperties props;

    // ---------- 商品详情 ----------

    public ProductDetailVO getDetail(Long id) {
        if (props.getProductDetailTtl() <= 0) {
            return null;
        }
        Object v = redis.opsForValue().get(KEY_DETAIL + id);
        return v instanceof ProductDetailVO vo ? vo : null;
    }

    public void putDetail(Long id, ProductDetailVO vo) {
        if (props.getProductDetailTtl() > 0 && vo != null) {
            redis.opsForValue().set(KEY_DETAIL + id, vo, props.getProductDetailTtl(), TimeUnit.SECONDS);
        }
    }

    /** 商品修改后失效,防脏数据。 */
    public void evictDetail(Long id) {
        redis.delete(KEY_DETAIL + id);
        log.debug("[cache] evict product:detail:{}", id);
    }

    // ---------- 分类列表 ----------

    @SuppressWarnings("unchecked")
    public List<Category> getCategoryList() {
        if (props.getCategoryListTtl() <= 0) {
            return null;
        }
        Object v = redis.opsForValue().get(KEY_CATEGORY_LIST);
        return v instanceof List<?> list ? (List<Category>) list : null;
    }

    public void putCategoryList(List<Category> list) {
        if (props.getCategoryListTtl() > 0 && list != null) {
            redis.opsForValue().set(KEY_CATEGORY_LIST, list, props.getCategoryListTtl(), TimeUnit.SECONDS);
        }
    }

    /** 分类修改(增/删/改)后失效。 */
    public void evictCategoryList() {
        redis.delete(KEY_CATEGORY_LIST);
        log.debug("[cache] evict product:category:list");
    }

    // ---------- 热门商品 ----------

    @SuppressWarnings("unchecked")
    public List<Product> getHot(int limit) {
        if (props.getHotProductsTtl() <= 0) {
            return null;
        }
        Object v = redis.opsForValue().get(KEY_HOT + limit);
        return v instanceof List<?> list ? (List<Product>) list : null;
    }

    public void putHot(int limit, List<Product> list) {
        if (props.getHotProductsTtl() > 0 && list != null) {
            redis.opsForValue().set(KEY_HOT + limit, list, props.getHotProductsTtl(), TimeUnit.SECONDS);
        }
    }

    /**
     * 商品修改可能影响销量,批量失效所有热门商品缓存。
     * 用 keys pattern 扫,单机 Redis 数据量小时没问题(骨架期够用);
     * 数据量大后期用 Redis Set 记录 hot 用过的 limit 值,精确删除。
     */
    public void evictHotAll() {
        var keys = redis.keys(KEY_HOT + "*");
        if (keys != null && !keys.isEmpty()) {
            redis.delete(keys);
            log.debug("[cache] evict {} hot keys", keys.size());
        }
    }
}
