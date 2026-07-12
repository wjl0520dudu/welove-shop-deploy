package com.welove.shop.chat.controller;

import com.welove.shop.chat.entity.KnowledgeDoc;
import com.welove.shop.chat.service.KnowledgeService;
import com.welove.shop.common.core.result.Result;
import com.welove.shop.common.storage.service.StorageService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.List;

@Slf4j
@RestController
@RequestMapping("/knowledge")
@RequiredArgsConstructor
public class KnowledgeController {
    private final KnowledgeService knowledgeService;
    private final StorageService storageService;

    /**
     * 上传知识库文档。
     * <p>走 {@link StorageService} 上传,具体后端是 OSS 还是本地磁盘由 common-storage 自动装配决定。
     * 存到数据库的 filePath 始终是可访问的完整 URL(由 {@link StorageService#getUrl} 拼出)。</p>
     */
    @PostMapping("/upload")
    public Result<KnowledgeDoc> upload(@RequestParam("file") MultipartFile file,
                                       @RequestParam Long categoryId) throws IOException {
        String original = file.getOriginalFilename();
        String objectKey = storageService.put(file);
        String url = storageService.getUrl(objectKey);
        String docType = (original != null && original.contains("."))
                ? original.substring(original.lastIndexOf('.') + 1)
                : "unknown";
        log.info("[KnowledgeController] upload 成功 key={} url={}", objectKey, url);
        return Result.ok(knowledgeService.uploadDoc(original, url, objectKey, categoryId, docType));
    }

    @GetMapping("/list")
    public Result<List<KnowledgeDoc>> list(@RequestParam(required = false) Long categoryId) {
        return Result.ok(knowledgeService.listDocs(categoryId));
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        knowledgeService.deleteDoc(id);
        return Result.ok();
    }
}
