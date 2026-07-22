package com.welove.shop.product.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.welove.shop.common.core.exception.BizException;
import com.welove.shop.common.core.exception.ErrorCode;
import com.welove.shop.common.core.result.Result;
import com.welove.shop.product.entity.Product;
import com.welove.shop.product.mapper.ProductMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 管理后台商品管理内部接口。
 * <p>
 * 供 admin-bff 调用,直接操作 ProductMapper 完成商品管理功能。
 */
@RestController
@RequestMapping("/internal/admin/product")
@RequiredArgsConstructor
public class InternalAdminController {

    private final ProductMapper productMapper;

    /**
     * 分页查询商品列表。
     *
     * @param keyword    搜索关键词(title / brand / tags)
     * @param page       页码
     * @param size       每页条数
     * @param sortBy     排序字段
     * @param sortOrder  排序方向
     */
    @GetMapping("/list")
    public Result<IPage<Product>> list(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Long categoryId,
            @RequestParam(required = false) String brand,
            @RequestParam(required = false) Integer status,
            @RequestParam(required = false) Double minPrice,
            @RequestParam(required = false) Double maxPrice,
            @RequestParam(defaultValue = "id") String sortBy,
            @RequestParam(defaultValue = "desc") String sortOrder) {

        LambdaQueryWrapper<Product> wrapper = new LambdaQueryWrapper<>();

        // 关键词搜索: title / brand / tags 任一匹配
        if (StringUtils.hasText(keyword)) {
            wrapper.and(w -> w
                    .like(Product::getTitle, keyword)
                    .or()
                    .like(Product::getBrand, keyword)
                    .or()
                    .like(Product::getTags, keyword));
        }

        if (categoryId != null) {
            wrapper.eq(Product::getCategoryId, categoryId);
        }
        if (StringUtils.hasText(brand)) {
            wrapper.eq(Product::getBrand, brand);
        }
        if (status != null) {
            wrapper.eq(Product::getStatus, status);
        }
        if (minPrice != null) {
            wrapper.ge(Product::getBasePrice, minPrice);
        }
        if (maxPrice != null) {
            wrapper.le(Product::getBasePrice, maxPrice);
        }

        // 排序
        boolean isAsc = "asc".equalsIgnoreCase(sortOrder);
        switch (sortBy) {
            case "price"    -> wrapper.orderBy(true, isAsc, Product::getBasePrice);
            case "sales"    -> wrapper.orderBy(true, isAsc, Product::getSalesCount);
            case "rating"   -> wrapper.orderBy(true, isAsc, Product::getRating);
            case "reviews"  -> wrapper.orderBy(true, isAsc, Product::getReviewCount);
            case "newest"   -> wrapper.orderBy(true, isAsc, Product::getCreateTime);
            case "title"    -> wrapper.orderBy(true, isAsc, Product::getTitle);
            default         -> wrapper.orderBy(true, isAsc, Product::getId);
        }

        return Result.ok(productMapper.selectPage(new Page<>(page, size), wrapper));
    }

    /**
     * 新增商品。
     * <p>
     * 骨架期最小字段：title / brand / categoryId / basePrice / imageUrl / description / tags / status。
     * 自动生成 productCode，${embeddingStatus} 初始化为 0（后续由 ai-service 同步脚本处理）。
     */
    @PostMapping
    public Result<Product> create(@RequestBody Product product) {
        product.setId(null);
        if (product.getProductCode() == null || product.getProductCode().isBlank()) {
            product.setProductCode("p_auto_" + System.currentTimeMillis());
        }
        if (product.getStatus() == null) {
            product.setStatus(1);
        }
        product.setEmbeddingStatus(0);
        product.setSalesCount(0);
        product.setReviewCount(0);
        product.setRating(java.math.BigDecimal.ZERO);
        product.setCreateTime(LocalDateTime.now());
        productMapper.insert(product);
        return Result.ok(productMapper.selectById(product.getId()));
    }

    /**
     * 更新商品上下架状态。
     *
     * @param id     商品 ID
     * @param status 目标状态: 1=上架, 0=下架
     */
    @PutMapping("/{id}/status")
    public Result<Void> updateStatus(@PathVariable Long id, @RequestParam int status) {
        Product product = productMapper.selectById(id);
        if (product == null) {
            throw new BizException(ErrorCode.NOT_FOUND);
        }
        product.setStatus(status);
        productMapper.updateById(product);
        return Result.ok();
    }

    /**
     * 更新商品信息。
     *
     * @param id      商品 ID
     * @param product 待更新的商品字段
     */
    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Long id, @RequestBody Product product) {
        product.setId(id);
        productMapper.updateById(product);
        return Result.ok();
    }

    /**
     * 商品统计概览。
     * <p>
     * 返回:
     * <ul>
     *   <li>total — 商品总数</li>
     *   <li>online — 上架商品数</li>
     *   <li>offline — 下架商品数</li>
     *   <li>brandDistribution — 品牌分布 top10</li>
     *   <li>categoryDistribution — 类目分布 top10</li>
     * </ul>
     */
    @GetMapping("/stats")
    public Result<Map<String, Object>> stats() {
        Map<String, Object> result = new HashMap<>();

        // 总数
        result.put("total", productMapper.selectCount(null));

        // 上架数
        LambdaQueryWrapper<Product> onlineWrapper = new LambdaQueryWrapper<>();
        onlineWrapper.eq(Product::getStatus, 1);
        result.put("online", productMapper.selectCount(onlineWrapper));

        // 下架数
        LambdaQueryWrapper<Product> offlineWrapper = new LambdaQueryWrapper<>();
        offlineWrapper.eq(Product::getStatus, 0);
        result.put("offline", productMapper.selectCount(offlineWrapper));

        // 品牌分布 top10
        QueryWrapper<Product> brandWrapper = new QueryWrapper<>();
        brandWrapper.select("brand, COUNT(*) as cnt")
                .isNotNull("brand")
                .groupBy("brand")
                .orderByDesc("cnt")
                .last("LIMIT 10");
        result.put("brandDistribution", productMapper.selectMaps(brandWrapper));

        // 类目分布 top10
        QueryWrapper<Product> categoryWrapper = new QueryWrapper<>();
        categoryWrapper.select("category_id, COUNT(*) as cnt")
                .isNotNull("category_id")
                .groupBy("category_id")
                .orderByDesc("cnt")
                .last("LIMIT 10");
        result.put("categoryDistribution", productMapper.selectMaps(categoryWrapper));

        return Result.ok(result);
    }

    /**
     * 品牌列表(去重)。
     */
    @GetMapping("/brands")
    public Result<List<String>> brands() {
        QueryWrapper<Product> wrapper = new QueryWrapper<>();
        wrapper.select("DISTINCT brand")
                .isNotNull("brand")
                .ne("brand", "")
                .orderByAsc("brand");
        List<Object> objects = productMapper.selectObjs(wrapper);
        return Result.ok(objects.stream().map(Object::toString).toList());
    }
}