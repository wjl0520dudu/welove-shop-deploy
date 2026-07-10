package com.welove.shop.product.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.welove.shop.product.entity.ProductSku;
import com.welove.shop.product.mapper.ProductSkuMapper;
import com.welove.shop.product.service.ProductSkuService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class ProductSkuServiceImpl implements ProductSkuService {

    private final ProductSkuMapper skuMapper;

    @Override
    public List<ProductSku> listByProductId(Long productId) {
        return skuMapper.selectList(
                new LambdaQueryWrapper<ProductSku>()
                        .eq(ProductSku::getProductId, productId)
                        .orderByDesc(ProductSku::getIsDefault));
    }

    @Override
    public int updateStock(Long skuId, Integer quantity) {
        return skuMapper.updateStock(skuId, quantity);
    }

    @Override
    public List<ProductSku> listByIds(List<Long> ids) {
        if (ids == null || ids.isEmpty()) {
            return List.of();
        }
        return skuMapper.selectByIds(ids);
    }
}
