package com.welove.shop.user.feign;

import com.welove.shop.common.core.result.Result;
import com.welove.shop.user.feign.dto.ProductDTO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 把 productId 列表通过 Feign 转成 id -> ProductDTO 的查表,供收藏/浏览历史回填展示字段。
 * <p>
 * 关键设计:
 * <ul>
 *   <li>Feign 失败/空响应时返回空 Map,不抛异常 —— user 域查询要稳,不能因为 product-service 抖动把整条列表拖垮。</li>
 *   <li>id 列表去重 + 过滤 null —— 避免一次浏览重复打 /product/batch。</li>
 *   <li>结果按 id 索引成 Map —— 方便调用方 O(1) 拿到。</li>
 * </ul>
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class ProductInfoEnricher {

    private final ProductClient productClient;

    /**
     * 批量拉取商品基础字段并按 id 索引。
     *
     * @param productIds 商品 id 集合(允许含重复/null,内部会去重过滤)
     * @return id -> ProductDTO;查不到或调用失败时返回空 Map
     */
    public Map<Long, ProductDTO> loadByIds(Collection<Long> productIds) {
        if (productIds == null || productIds.isEmpty()) {
            return Collections.emptyMap();
        }
        List<Long> ids = productIds.stream()
                .filter(java.util.Objects::nonNull)
                .distinct()
                .collect(Collectors.toList());
        if (ids.isEmpty()) {
            return Collections.emptyMap();
        }
        try {
            Result<List<ProductDTO>> resp = productClient.batch(ids);
            if (resp == null || resp.getData() == null) {
                log.warn("[enrich] product-service /product/batch returned null data, ids={}", ids);
                return Collections.emptyMap();
            }
            return resp.getData().stream()
                    .filter(java.util.Objects::nonNull)
                    .filter(p -> p.getId() != null)
                    .collect(Collectors.toMap(p -> p.getId(), p -> p, (a, b) -> a));
        } catch (Exception e) {
            // Feign 调用失败不能让 user 域列表挂掉 —— 走空 Map 兜底,前端会显示「商品已下架」之类的占位
            log.error("[enrich] product-service batch failed, ids={}", ids, e);
            return Collections.emptyMap();
        }
    }
}