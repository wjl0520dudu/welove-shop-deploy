package com.welove.shop.chat.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.welove.shop.chat.entity.Conversation;
import com.welove.shop.chat.entity.Message;
import com.welove.shop.chat.mapper.ConversationMapper;
import com.welove.shop.chat.mapper.MessageMapper;
import com.welove.shop.common.core.result.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 内部管理后台接口 —— 会话管理。
 * <p>供 admin-bff 调用,直接操作 Mapper 不经过 Service 层。</p>
 */
@RestController
@RequestMapping("/internal/admin/conversation")
@RequiredArgsConstructor
public class InternalAdminConversationController {

    private final ConversationMapper conversationMapper;
    private final MessageMapper messageMapper;

    /**
     * 分页查询会话列表,支持 userId 和 keyword(标题) 筛选,按 update_time 降序。
     * 返回时给每个会话补上 messageCount 字段。
     */
    @GetMapping("/list")
    public Result<IPage<Conversation>> list(@RequestParam(defaultValue = "1") int page,
                                            @RequestParam(defaultValue = "10") int size,
                                            @RequestParam(required = false) Long userId,
                                            @RequestParam(required = false) String keyword) {
        LambdaQueryWrapper<Conversation> wrapper = Wrappers.lambdaQuery(Conversation.class)
                .orderByDesc(Conversation::getUpdateTime);

        if (userId != null) {
            wrapper.eq(Conversation::getUserId, userId);
        }
        if (keyword != null && !keyword.isBlank()) {
            wrapper.like(Conversation::getTitle, keyword);
        }

        IPage<Conversation> pageResult = conversationMapper.selectPage(new Page<>(page, size), wrapper);

        // 补上 messageCount
        for (Conversation conversation : pageResult.getRecords()) {
            Long count = messageMapper.selectCount(
                    Wrappers.lambdaQuery(Message.class)
                            .eq(Message::getConversationId, conversation.getId())
            );
            conversation.setMessageCount(count.intValue());
        }

        return Result.ok(pageResult);
    }

    /**
     * 查询指定会话的所有消息,按 create_time 升序。
     */
    @GetMapping("/{id}/messages")
    public Result<List<Message>> messages(@PathVariable Long id) {
        List<Message> messages = messageMapper.selectList(
                Wrappers.lambdaQuery(Message.class)
                        .eq(Message::getConversationId, id)
                        .orderByAsc(Message::getCreateTime)
        );
        return Result.ok(messages);
    }

    /**
     * 统计:totalConversations, totalMessages, todayConversations。
     */
    @GetMapping("/stats")
    public Result<Map<String, Object>> stats() {
        long totalConversations = conversationMapper.selectCount(null);
        long totalMessages = messageMapper.selectCount(null);

        LocalDateTime todayStart = LocalDateTime.of(LocalDate.now(), LocalTime.MIN);
        long todayConversations = conversationMapper.selectCount(
                Wrappers.lambdaQuery(Conversation.class)
                        .ge(Conversation::getCreateTime, todayStart)
        );

        Map<String, Object> stats = new HashMap<>();
        stats.put("totalConversations", totalConversations);
        stats.put("totalMessages", totalMessages);
        stats.put("todayConversations", todayConversations);
        return Result.ok(stats);
    }

    /**
     * 删除会话及其所有消息。
     */
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        messageMapper.delete(
                Wrappers.lambdaQuery(Message.class)
                        .eq(Message::getConversationId, id)
        );
        conversationMapper.deleteById(id);
        return Result.ok();
    }
}