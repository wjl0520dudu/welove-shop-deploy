package com.welove.shop.chat.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.welove.shop.chat.entity.Conversation;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface ConversationMapper extends BaseMapper<Conversation> {
}
