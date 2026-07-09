package com.welove.shop.user.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.welove.shop.user.entity.User;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface UserMapper extends BaseMapper<User> {
}
