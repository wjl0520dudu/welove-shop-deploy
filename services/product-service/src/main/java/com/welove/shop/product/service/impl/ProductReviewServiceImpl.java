package com.welove.shop.product.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.welove.shop.common.core.exception.BizException;
import com.welove.shop.product.entity.ProductReview;
import com.welove.shop.product.exception.ProductErrorCode;
import com.welove.shop.product.mapper.ProductReviewMapper;
import com.welove.shop.product.service.ProductReviewService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.List;

@Service
@RequiredArgsConstructor
public class ProductReviewServiceImpl implements ProductReviewService {

    private final ProductReviewMapper reviewMapper;

    @Override
    public List<ProductReview> listByProductId(Long productId, int limit) {
        return reviewMapper.selectList(
                new LambdaQueryWrapper<ProductReview>()
                        .eq(ProductReview::getProductId, productId)
                        .orderByDesc(ProductReview::getCreateTime)
                        .last("LIMIT " + limit));
    }

    @Override
    public ProductReview submit(ProductReview review) {
        if (review.getRating() == null || review.getRating() < 1 || review.getRating() > 5) {
            throw new BizException(ProductErrorCode.REVIEW_INVALID_RATING, "评分必须在 1-5 之间");
        }
        if (!StringUtils.hasText(review.getContent())) {
            throw new BizException(ProductErrorCode.REVIEW_CONTENT_EMPTY, "评价内容不能为空");
        }
        review.setCreateTime(LocalDateTime.now());
        reviewMapper.insert(review);
        return review;
    }
}
