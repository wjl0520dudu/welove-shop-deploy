package com.welove.shop.chat.service;

import com.welove.shop.chat.entity.Notice;
import java.util.List;

public interface NoticeService {
    List<Notice> getActiveNotices();
}
