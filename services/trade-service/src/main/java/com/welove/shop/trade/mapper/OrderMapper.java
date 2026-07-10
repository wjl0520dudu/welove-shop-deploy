package com.welove.shop.trade.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.welove.shop.trade.entity.Order;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface OrderMapper extends BaseMapper<Order> {
}
