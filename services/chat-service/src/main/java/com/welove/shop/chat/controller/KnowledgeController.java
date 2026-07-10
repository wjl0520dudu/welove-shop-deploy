package com.welove.shop.chat.controller;

import com.welove.shop.chat.entity.KnowledgeDoc;
import com.welove.shop.chat.service.KnowledgeService;
import com.welove.shop.common.core.result.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.IOException;
import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/knowledge")
@RequiredArgsConstructor
public class KnowledgeController {
    private final KnowledgeService knowledgeService;

    @PostMapping("/upload") public Result<KnowledgeDoc> upload(@RequestParam("file") MultipartFile file, @RequestParam Long categoryId) throws IOException {
        // 简单本地存储:TODO 云存储
        String fileName = file.getOriginalFilename();
        String localPath = "tmp/knowledge/" + UUID.randomUUID() + "_" + fileName;
        File dest = new File(localPath);
        dest.getParentFile().mkdirs();
        file.transferTo(dest);
        return Result.ok(knowledgeService.uploadDoc(fileName, localPath, categoryId, fileName != null ? fileName.substring(fileName.lastIndexOf('.') + 1) : "unknown"));
    }
    @GetMapping("/list") public Result<List<KnowledgeDoc>> list(@RequestParam(required = false) Long categoryId) {
        return Result.ok(knowledgeService.listDocs(categoryId));
    }
    @DeleteMapping("/{id}") public Result<Void> delete(@PathVariable Long id) {
        knowledgeService.deleteDoc(id); return Result.ok();
    }
}
