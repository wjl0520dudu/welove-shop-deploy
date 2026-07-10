package com.welove.shop.chat.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.welove.shop.chat.entity.KnowledgeDoc;
import com.welove.shop.chat.mapper.KnowledgeDocMapper;
import com.welove.shop.chat.service.AiService;
import com.welove.shop.chat.service.KnowledgeService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

/** 知识库 CRUD，移除七牛云引用，用本地存储(TODO 云存储)。 */
@Slf4j
@Service
@RequiredArgsConstructor
public class KnowledgeServiceImpl implements KnowledgeService {
    private final KnowledgeDocMapper docMapper;
    private final AiService aiService;

    @Override
    public KnowledgeDoc uploadDoc(String fileName, String filePath, Long categoryId, String docType) {
        KnowledgeDoc doc = new KnowledgeDoc();
        doc.setDocName(fileName);
        doc.setFilePath(filePath);
        doc.setCategoryId(categoryId);
        doc.setDocType(docType);
        doc.setStatus("PENDING");
        doc.setCreateTime(LocalDateTime.now());
        docMapper.insert(doc);
        aiService.parseDocument(filePath, doc.getId());
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
            // TODO 云存储:清理文件
            aiService.deleteDoc(docId);
            docMapper.deleteById(docId);
        }
    }
}
