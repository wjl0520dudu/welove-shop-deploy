package com.welove.shop.admin.controller;

import com.welove.shop.admin.feign.AdminChatClient;
import com.welove.shop.common.core.result.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 管理端公告管理 —— Feign 透传 chat-service /internal/admin/notice。
 */
@RestController
@RequestMapping("/notice")
@RequiredArgsConstructor
public class AdminNoticeController {

    private final AdminChatClient chat;

    @GetMapping("/list")
    public Result<Map<String, Object>> list(@RequestParam(defaultValue = "1") int page,
                                            @RequestParam(defaultValue = "10") int size) {
        return chat.noticeList(page, size);
    }

    @PostMapping("/add")
    public Result<String> add(@RequestBody Map<String, Object> notice) {
        return chat.noticeAdd(notice);
    }

    @PutMapping("/update")
    public Result<String> update(@RequestBody Map<String, Object> notice) {
        return chat.noticeUpdate(notice);
    }

    @DeleteMapping("/delete/{id}")
    public Result<String> delete(@PathVariable Long id) {
        return chat.noticeDelete(id);
    }
}
