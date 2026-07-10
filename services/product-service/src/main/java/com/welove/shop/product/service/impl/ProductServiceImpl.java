package com.welove.shop.product.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.welove.shop.common.core.exception.BizException;
import com.welove.shop.product.cache.ProductCache;
import com.welove.shop.product.entity.Product;
import com.welove.shop.product.exception.ProductErrorCode;
import com.welove.shop.product.mapper.ProductMapper;
import com.welove.shop.product.service.ProductFaqService;
import com.welove.shop.product.service.ProductImageService;
import com.welove.shop.product.service.ProductReviewService;
import com.welove.shop.product.service.ProductService;
import com.welove.shop.product.service.ProductSkuService;
import com.welove.shop.product.vo.ProductDetailVO;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 商品服务实现。
 * <p>
 * 搜索为 LIKE MVP:同义词扩展 + 相关性打分。后续同分支加 RAG 向量搜索(不删本实现,保留兜底)。
 */
@Service
@RequiredArgsConstructor
public class ProductServiceImpl implements ProductService {

    private final ProductMapper productMapper;
    private final ProductSkuService skuService;
    private final ProductImageService imageService;
    private final ProductFaqService faqService;
    private final ProductReviewService reviewService;
    private final ProductCache cache;

    // ---------- 列表 ----------

    @Override
    public IPage<Product> listByCategory(Long categoryId, int page, int size, String sortBy, String sortOrder) {
        LambdaQueryWrapper<Product> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Product::getStatus, 1);
        if (categoryId != null) {
            wrapper.eq(Product::getCategoryId, categoryId);
        }

        boolean isAsc = "asc".equalsIgnoreCase(sortOrder);
        String by = sortBy == null ? "sales" : sortBy;
        switch (by) {
            case "price"   -> wrapper.orderBy(true, isAsc, Product::getBasePrice);
            case "rating"  -> wrapper.orderBy(true, isAsc, Product::getRating);
            case "reviews" -> wrapper.orderBy(true, isAsc, Product::getReviewCount);
            case "newest"  -> wrapper.orderBy(true, isAsc, Product::getCreateTime);
            default        -> wrapper.orderByDesc(Product::getSalesCount);
        }

        return productMapper.selectPage(new Page<>(page, size), wrapper);
    }

    // ---------- 单条 / 详情聚合 ----------

    @Override
    public Product getById(Long id) {
        Product p = productMapper.selectById(id);
        if (p == null) {
            throw new BizException(ProductErrorCode.PRODUCT_NOT_FOUND, "商品不存在");
        }
        return p;
    }

    @Override
    public ProductDetailVO getDetail(Long id) {
        ProductDetailVO cached = cache.getDetail(id);
        if (cached != null) {
            return cached;
        }
        Product product = getById(id);
        ProductDetailVO vo = new ProductDetailVO();
        vo.setProduct(product);
        vo.setSkus(skuService.listByProductId(id));
        vo.setImages(imageService.listByProductId(id));
        vo.setFaqs(faqService.listByProductId(id));
        vo.setReviews(reviewService.listByProductId(id, 10));
        cache.putDetail(id, vo);
        return vo;
    }

    // ---------- 搜索(同义词扩展 + LIKE + 打分) ----------

    /** 常用同义词扩展表,与 monolith 保持一致。 */
    private static final Map<String, List<String>> SYNONYM_MAP = new HashMap<>();
    static {
        // 服饰大类
        SYNONYM_MAP.put("衣服", Arrays.asList("卫衣", "T恤", "衬衫", "外套", "夹克", "短袖", "长袖"));
        SYNONYM_MAP.put("裤子", Arrays.asList("牛仔裤", "休闲裤", "运动裤", "长裤", "短裤", "工装裤", "西裤"));
        SYNONYM_MAP.put("鞋",   Arrays.asList("运动鞋", "跑步鞋", "篮球鞋", "板鞋", "休闲鞋", "帆布鞋"));
        SYNONYM_MAP.put("鞋子", Arrays.asList("运动鞋", "跑步鞋", "篮球鞋", "板鞋", "休闲鞋", "帆布鞋"));
        // 运动鞋细分
        SYNONYM_MAP.put("跑鞋",   Arrays.asList("跑步鞋", "运动鞋", "马拉松鞋"));
        SYNONYM_MAP.put("篮球鞋", Arrays.asList("篮球鞋", "高帮球鞋", "实战篮球鞋"));
        // 护肤大类
        SYNONYM_MAP.put("护肤品", Arrays.asList("精华", "面霜", "乳液", "爽肤水", "化妆水", "面膜", "眼霜", "防晒"));
        SYNONYM_MAP.put("化妆品", Arrays.asList("口红", "粉底", "眼影", "腮红", "遮瑕", "气垫", "散粉"));
        SYNONYM_MAP.put("护肤",   Arrays.asList("精华", "面霜", "乳液", "爽肤水", "面膜", "眼霜"));
        // 护肤细分
        SYNONYM_MAP.put("面膜", Arrays.asList("面膜", "贴片面膜", "涂抹面膜", "睡眠面膜"));
        SYNONYM_MAP.put("精华", Arrays.asList("精华液", "精华露", "肌底液", "安瓶"));
        SYNONYM_MAP.put("防晒", Arrays.asList("防晒霜", "防晒喷雾", "防晒乳", "隔离霜"));
        // 数码
        SYNONYM_MAP.put("手机", Arrays.asList("手机", "智能手机", "5G手机"));
        SYNONYM_MAP.put("耳机", Arrays.asList("蓝牙耳机", "无线耳机", "头戴耳机", "降噪耳机", "运动耳机"));
        // 食品
        SYNONYM_MAP.put("零食", Arrays.asList("坚果", "饼干", "薯片", "巧克力", "糖果", "肉脯"));
        SYNONYM_MAP.put("饮料", Arrays.asList("气泡水", "果汁", "茶饮", "咖啡", "矿泉水", "苏打水"));
    }

    @Override
    public List<Product> search(String keyword, int limit) {
        if (keyword == null || keyword.isEmpty()) {
            return List.of();
        }

        // 原词 + 扩展词
        List<String> terms = new ArrayList<>();
        terms.add(keyword);
        if (SYNONYM_MAP.containsKey(keyword)) {
            terms.addAll(SYNONYM_MAP.get(keyword));
        }

        // 每个词单独搜,LinkedHashMap 按 id 去重(保留首个出现顺序,便于后续打分排序稳定)
        Map<Long, Product> unique = new LinkedHashMap<>();
        for (String term : terms) {
            List<Product> results = productMapper.selectList(
                    new LambdaQueryWrapper<Product>()
                            .eq(Product::getStatus, 1)
                            .and(w -> w.like(Product::getTitle, term)
                                    .or().like(Product::getBrand, term)
                                    .or().like(Product::getTags, term)
                                    .or().like(Product::getDescription, term))
                            .last("LIMIT 20"));
            for (Product p : results) {
                unique.putIfAbsent(p.getId(), p);
            }
        }

        // 相关性打分:title+3 / brand+2 / tags+2 / description+1,同分按销量降序
        return unique.values().stream()
                .sorted((a, b) -> {
                    int sa = score(a, keyword);
                    int sb = score(b, keyword);
                    if (sb != sa) {
                        return sb - sa;
                    }
                    int salesA = a.getSalesCount() == null ? 0 : a.getSalesCount();
                    int salesB = b.getSalesCount() == null ? 0 : b.getSalesCount();
                    return salesB - salesA;
                })
                .limit(limit)
                .collect(Collectors.toList());
    }

    private int score(Product p, String keyword) {
        int s = 0;
        if (p.getTitle() != null && p.getTitle().contains(keyword))       s += 3;
        if (p.getBrand() != null && p.getBrand().contains(keyword))       s += 2;
        if (p.getTags()  != null && p.getTags().contains(keyword))        s += 2;
        if (p.getDescription() != null && p.getDescription().contains(keyword)) s += 1;
        return s;
    }

    // ---------- 热门商品 ----------

    @Override
    public List<Product> getHotProducts(int limit) {
        List<Product> cached = cache.getHot(limit);
        if (cached != null) {
            return cached;
        }
        List<Product> fresh = productMapper.selectList(
                new LambdaQueryWrapper<Product>()
                        .eq(Product::getStatus, 1)
                        .orderByDesc(Product::getSalesCount)
                        .last("LIMIT " + limit));
        cache.putHot(limit, fresh);
        return fresh;
    }
}
