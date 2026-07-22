package com.welove.shop.chat.service;

import com.welove.shop.chat.entity.KnowledgeDoc;
import java.util.List;

public interface KnowledgeService {
    /**
     * @param fileName 原始文件名
     * @param filePath 对外可访问的 URL(由 {@code StorageService.getUrl(key)} 拼出)
     * @param objectKey 对象存储内部的 key,用于删除/查重
     * @param categoryId 分类
     * @param docType 扩展名(pdf/docx/txt/...)
     */
    KnowledgeDoc uploadDoc(String fileName, String filePath, String objectKey, Long categoryId, String docType);
    List<KnowledgeDoc> listDocs(Long categoryId);
    void deleteDoc(Long docId);
}
