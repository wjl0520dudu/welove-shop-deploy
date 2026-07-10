package com.welove.shop.trade.feign;

import com.welove.shop.common.core.result.Result;
import com.welove.shop.trade.feign.dto.AddressDTO;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;

/**
 * 调 user-service 的 Feign 客户端。
 * <p>
 * 用途:下单时按 addressId 查地址,把 receiverName/phone/省市区/详细拼接后写入 order 快照。
 */
@FeignClient(name = "user-service", contextId = "userClient")
public interface UserClient {

    /** 内部接口:按 ID 查地址(不校验归属,免登录,只允许集群内 Feign 调用)。 */
    @GetMapping("/api/internal/address/{id}")
    Result<AddressDTO> getAddress(@PathVariable Long id);
}
