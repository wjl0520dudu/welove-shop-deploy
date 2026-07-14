package com.welove.shop.admin.controller;

import com.welove.shop.admin.feign.AdminChatClient;
import com.welove.shop.common.core.result.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 管理端知识库管理 —— Feign 透传 chat-service /internal/admin/knowledge。
 * <p>知识库上传 upload 涉及 MultipartFile 转发,单独通过 chat-service 已有的
 * /api/chat/knowledge/upload 接口处理,这里只暴露列表/删除/重试解析。</p>
 */
@RestController
@RequestMapping("/knowledge")
@RequiredArgsConstructor
public class AdminKnowledgeController {

    private final AdminChatClient chat;

    @GetMapping("/list")
    public Result<List<Map<String, Object>>> list(@RequestParam(required = false) Long categoryId) {
        return chat.knowledgeList(categoryId);
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        return chat.knowledgeDelete(id);
    }

    @PostMapping("/retry-parse")
    public Result<Void> retryParse(@RequestBody Map<String, Object> request) {
        return chat.knowledgeRetryParse(request);
    }
}
