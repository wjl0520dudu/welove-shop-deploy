package com.welove.shop.chat.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.welove.shop.chat.entity.KnowledgeDoc;
import com.welove.shop.chat.mapper.KnowledgeDocMapper;
import com.welove.shop.chat.service.AiService;
import com.welove.shop.chat.service.KnowledgeService;
import com.welove.shop.common.core.result.Result;
import com.welove.shop.common.storage.service.StorageService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.List;
import java.util.Map;

/**
 * 内部管理后台知识库接口 —— 供 admin-bff 调用。
 */
@Slf4j
@RestController
@RequestMapping("/internal/admin/knowledge")
@RequiredArgsConstructor
public class InternalAdminKnowledgeController {

    private final KnowledgeDocMapper knowledgeDocMapper;
    private final KnowledgeService knowledgeService;
    private final AiService aiService;
    private final StorageService storageService;

    /**
     * 查询知识库文档列表，支持按分类筛选。
     */
    @GetMapping("/list")
    public Result<List<KnowledgeDoc>> list(@RequestParam(required = false) Long categoryId) {
        LambdaQueryWrapper<KnowledgeDoc> wrapper = new LambdaQueryWrapper<KnowledgeDoc>()
                .eq(categoryId != null, KnowledgeDoc::getCategoryId, categoryId)
                .orderByDesc(KnowledgeDoc::getCreateTime);
        return Result.ok(knowledgeDocMapper.selectList(wrapper));
    }

    /**
     * 上传知识库文档。
     * <p>走 {@link StorageService} 上传，具体后端是 OSS 还是本地磁盘由 common-storage 自动装配决定。</p>
     */
    @PostMapping("/upload")
    public Result<KnowledgeDoc> upload(@RequestParam("file") MultipartFile file,
                                       @RequestParam(required = false) Long categoryId) throws IOException {
        String original = file.getOriginalFilename();
        String objectKey = storageService.put(file);
        String url = storageService.getUrl(objectKey);
        String docType = (original != null && original.contains("."))
                ? original.substring(original.lastIndexOf('.') + 1)
                : "unknown";
        log.info("[InternalAdminKnowledgeController] upload 成功 key={} url={}", objectKey, url);
        return Result.ok(knowledgeService.uploadDoc(original, url, objectKey, categoryId, docType));
    }

    /**
     * 删除知识库文档（同时清除向量索引）。
     */
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        knowledgeService.deleteDoc(id);
        return Result.ok();
    }

    /**
     * 重新解析文档（异步）。
     */
    @PostMapping("/retry-parse")
    public Result<Void> retryParse(@RequestBody Map<String, Object> request) {
        Long id = Long.valueOf(request.get("id").toString());
        String filePath = (String) request.get("filePath");
        aiService.parseDocument(filePath, null, id);
        return Result.ok();
    }
}