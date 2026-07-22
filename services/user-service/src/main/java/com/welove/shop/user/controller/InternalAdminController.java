package com.welove.shop.user.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.welove.shop.common.core.result.Result;
import com.welove.shop.user.entity.User;
import com.welove.shop.user.mapper.UserMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 管理员后台用户管理内部接口。
 * <p>
 * 路径前缀 /internal/admin 全部走白名单,不校验 JWT(骨架期)。
 * 供 admin-bff 调用,直接操作数据库,不经过 service 层。
 */
@RestController
@RequestMapping("/internal/admin")
@RequiredArgsConstructor
public class InternalAdminController {

    private final UserMapper userMapper;

    /**
     * 分页查询用户列表。
     *
     * @param page    当前页码
     * @param size    每页条数
     * @param keyword 搜索关键字,模糊匹配 username 或 phone
     * @return 分页用户列表
     */
    @GetMapping("/users")
    public Result<IPage<User>> listUsers(@RequestParam(defaultValue = "1") long page,
                                         @RequestParam(defaultValue = "10") long size,
                                         @RequestParam(required = false) String keyword) {
        Page<User> pageParam = new Page<>(page, size);
        LambdaQueryWrapper<User> wrapper = new LambdaQueryWrapper<>();
        if (keyword != null && !keyword.isBlank()) {
            wrapper.and(w -> w
                    .like(User::getUsername, keyword)
                    .or()
                    .like(User::getPhone, keyword)
            );
        }
        wrapper.orderByDesc(User::getCreateTime);
        return Result.ok(userMapper.selectPage(pageParam, wrapper));
    }

    /**
     * 更新用户状态。
     *
     * @param id     用户 ID
     * @param status 状态值: 1=正常, 0=禁用
     * @return 操作结果
     */
    @PutMapping("/users/{id}/status")
    public Result<Void> updateUserStatus(@PathVariable Long id,
                                         @RequestParam Integer status) {
        User user = new User();
        user.setId(id);
        user.setStatus(status);
        userMapper.updateById(user);
        return Result.ok();
    }
}