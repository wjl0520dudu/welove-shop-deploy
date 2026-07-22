package com.welove.shop.admin.feign;

import com.welove.shop.common.core.result.Result;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestParam;

import java.util.Map;

/**
 * user-service admin 内部接口 Feign 客户端。
 * <p>直接透传 Map 返回体,由 admin-bff Controller 层再直接透传给前端。</p>
 */
@FeignClient(name = "user-service", contextId = "adminUserClient")
public interface AdminUserClient {

    /** 分页查询用户列表,支持 keyword 模糊匹配。 */
    @GetMapping("/internal/admin/users")
    Result<Map<String, Object>> users(@RequestParam(defaultValue = "1") Integer page,
                                      @RequestParam(defaultValue = "10") Integer size,
                                      @RequestParam(required = false) String keyword);

    /** 更新用户状态。 */
    @PutMapping("/internal/admin/users/{id}/status")
    Result<Void> updateStatus(@PathVariable("id") Long id,
                              @RequestParam("status") Integer status);
}
