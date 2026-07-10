package com.welove.shop.product.controller;

import com.welove.shop.common.core.exception.BizException;
import com.welove.shop.common.core.exception.ErrorCode;
import com.welove.shop.common.core.result.Result;
import com.welove.shop.common.security.context.UserContext;
import com.welove.shop.product.entity.ProductFaq;
import com.welove.shop.product.entity.ProductImage;
import com.welove.shop.product.entity.ProductReview;
import com.welove.shop.product.entity.ProductSku;
import com.welove.shop.product.service.ProductFaqService;
import com.welove.shop.product.service.ProductImageService;
import com.welove.shop.product.service.ProductReviewService;
import com.welove.shop.product.service.ProductSkuService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 商品资源(SKU / Image / FAQ / Review)Controller。
 * <p>
 * 单独暴露以支持前端按需请求(如切换 SKU、图片轮播、FAQ 折叠)。
 * <p>
 * <b>评价列表(GET reviews)不在此单独暴露</b> —— 已包含在
 * {@code GET /api/product/{id}} 的详情聚合中(见 {@link com.welove.shop.product.vo.ProductDetailVO}),
 * 前端从详情接口一次拿到,不用二次请求。
 * <p>
 * 只暴露 POST /api/product/{id}/reviews 用于提交评价,需登录。
 */
@RestController
@RequestMapping("/api/product")
@RequiredArgsConstructor
public class ProductResourceController {

    private final ProductSkuService skuService;
    private final ProductImageService imageService;
    private final ProductFaqService faqService;
    private final ProductReviewService reviewService;

    // ---------- SKU ----------

    @GetMapping("/{id}/skus")
    public Result<List<ProductSku>> skus(@PathVariable Long id) {
        return Result.ok(skuService.listByProductId(id));
    }

    /**
     * 批量按 SKU ID 查(供 Feign 下游 trade-service 下单查 SKU 价格/属性)。
     * <p>
     * 路径避开 {@code /{id}/skus},用 /sku/batch 独立入口。
     */
    @GetMapping("/sku/batch")
    public Result<List<ProductSku>> skuBatch(@RequestParam List<Long> ids) {
        return Result.ok(skuService.listByIds(ids));
    }

    // ---------- 图片 ----------

    @GetMapping("/{id}/images")
    public Result<List<ProductImage>> images(@PathVariable Long id) {
        return Result.ok(imageService.listByProductId(id));
    }

    // ---------- FAQ ----------

    @GetMapping("/{id}/faqs")
    public Result<List<ProductFaq>> faqs(@PathVariable Long id) {
        return Result.ok(faqService.listByProductId(id));
    }

    // ---------- 评价:仅提交(GET 走详情聚合) ----------

    /**
     * 提交评价。
     * <p>
     * 需登录。userId 从 UserContext 拿(拦截器写入),覆盖客户端传入,防越权。
     */
    @PostMapping("/{id}/reviews")
    public Result<ProductReview> submitReview(@PathVariable Long id, @RequestBody ProductReview review) {
        Long userId = UserContext.getUserId();
        if (userId == null) {
            throw new BizException(ErrorCode.UNAUTHORIZED);
        }
        review.setProductId(id);
        review.setUserId(userId);
        return Result.ok(reviewService.submit(review));
    }
}
