package com.welove.shop.product.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.welove.shop.product.entity.ProductSku;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface ProductSkuMapper extends BaseMapper<ProductSku> {

    /**
     * 库存增减(原子操作)。
     * quantity 正数为增,负数为减(减到负值不会拦截,库存策略在 service 层)。
     */
    @Update("UPDATE product_svc.product_sku SET stock = stock + #{quantity} WHERE id = #{skuId}")
    int updateStock(Long skuId, Integer quantity);
}
