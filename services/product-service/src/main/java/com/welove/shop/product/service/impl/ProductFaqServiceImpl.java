package com.welove.shop.product.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.welove.shop.product.entity.ProductFaq;
import com.welove.shop.product.mapper.ProductFaqMapper;
import com.welove.shop.product.service.ProductFaqService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class ProductFaqServiceImpl implements ProductFaqService {

    private final ProductFaqMapper faqMapper;

    @Override
    public List<ProductFaq> listByProductId(Long productId) {
        return faqMapper.selectList(
                new LambdaQueryWrapper<ProductFaq>()
                        .eq(ProductFaq::getProductId, productId)
                        .orderByAsc(ProductFaq::getSortOrder));
    }
}
