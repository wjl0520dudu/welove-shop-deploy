package com.welove.shop.chat.controller;

import com.welove.shop.chat.entity.Notice;
import com.welove.shop.chat.service.NoticeService;
import com.welove.shop.common.core.result.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/notice")
@RequiredArgsConstructor
public class NoticeController {
    private final NoticeService noticeService;
    @GetMapping("/latest") public Result<List<Notice>> latest() {
        return Result.ok(noticeService.getActiveNotices());
    }
}
