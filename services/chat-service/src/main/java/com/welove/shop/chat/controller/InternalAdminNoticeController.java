package com.welove.shop.chat.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.welove.shop.chat.entity.Notice;
import com.welove.shop.chat.mapper.NoticeMapper;
import com.welove.shop.common.core.result.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

/**
 * 内部管理后台接口 —— 公告管理。
 * <p>供 admin-bff 调用,直接操作 Mapper 不经过 Service 层。</p>
 */
@RestController
@RequestMapping("/internal/admin/notice")
@RequiredArgsConstructor
public class InternalAdminNoticeController {

    private final NoticeMapper noticeMapper;

    /**
     * 分页查询公告列表,按 create_time 降序。
     */
    @GetMapping("/list")
    public Result<IPage<Notice>> list(@RequestParam(defaultValue = "1") int page,
                                      @RequestParam(defaultValue = "10") int size) {
        LambdaQueryWrapper<Notice> wrapper = Wrappers.lambdaQuery(Notice.class)
                .orderByDesc(Notice::getCreateTime);
        IPage<Notice> pageResult = noticeMapper.selectPage(new Page<>(page, size), wrapper);
        return Result.ok(pageResult);
    }

    /**
     * 新增公告。
     */
    @PostMapping("/add")
    public Result<String> add(@RequestBody Notice notice) {
        noticeMapper.insert(notice);
        return Result.ok("发布成功");
    }

    /**
     * 更新公告。
     */
    @PutMapping("/update")
    public Result<String> update(@RequestBody Notice notice) {
        noticeMapper.updateById(notice);
        return Result.ok("更新成功");
    }

    /**
     * 删除公告。
     */
    @DeleteMapping("/delete/{id}")
    public Result<String> delete(@PathVariable Long id) {
        noticeMapper.deleteById(id);
        return Result.ok("删除成功");
    }
}