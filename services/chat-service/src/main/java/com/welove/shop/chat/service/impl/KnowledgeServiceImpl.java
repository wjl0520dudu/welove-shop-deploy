package com.welove.shop.chat.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.welove.shop.chat.entity.KnowledgeDoc;
import com.welove.shop.chat.mapper.KnowledgeDocMapper;
import com.welove.shop.chat.service.AiService;
import com.welove.shop.chat.service.KnowledgeService;
import com.welove.shop.common.storage.service.StorageService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

/** 知识库 CRUD,接入云存储后 filePath 存公共 URL,objectKey 存对象 key。 */
@Slf4j
@Service
@RequiredArgsConstructor
public class KnowledgeServiceImpl implements KnowledgeService {
    private final KnowledgeDocMapper docMapper;
    private final AiService aiService;
    private final StorageService storageService;

    @Override
    public KnowledgeDoc uploadDoc(String fileName, String filePath, String objectKey,
                                  Long categoryId, String docType) {
        KnowledgeDoc doc = new KnowledgeDoc();
        doc.setDocName(fileName);
        doc.setFilePath(filePath);
        doc.setObjectKey(objectKey);
        doc.setCategoryId(categoryId);
        doc.setDocType(docType);
        doc.setStatus("PENDING");
        doc.setCreateTime(LocalDateTime.now());
        docMapper.insert(doc);
        // 传完整 URL 给 ai-service(公共读模式下,ai-service 用 httpx.get 拉取)
        aiService.parseDocument(filePath, objectKey, doc.getId());
        return doc;
    }

    @Override
    public List<KnowledgeDoc> listDocs(Long categoryId) {
        LambdaQueryWrapper<KnowledgeDoc> w = new LambdaQueryWrapper<KnowledgeDoc>()
                .orderByDesc(KnowledgeDoc::getCreateTime);
        if (categoryId != null) w.eq(KnowledgeDoc::getCategoryId, categoryId);
        return docMapper.selectList(w);
    }

    @Override
    public void deleteDoc(Long docId) {
        KnowledgeDoc doc = docMapper.selectById(docId);
        if (doc != null) {
            // 优先用 objectKey 删(更可靠,不受 CDN/域名变更影响)
            if (doc.getObjectKey() != null && !doc.getObjectKey().isBlank()) {
                try {
                    storageService.delete(doc.getObjectKey());
                } catch (Exception e) {
                    log.warn("[KnowledgeService] 删除对象失败 key={} err={}", doc.getObjectKey(), e.getMessage());
                }
            }
            aiService.deleteDoc(docId);
            docMapper.deleteById(docId);
        }
    }
}
