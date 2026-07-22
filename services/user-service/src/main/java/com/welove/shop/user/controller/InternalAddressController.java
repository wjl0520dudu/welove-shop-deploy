package com.welove.shop.user.controller;

import com.welove.shop.common.core.exception.BizException;
import com.welove.shop.common.core.exception.ErrorCode;
import com.welove.shop.common.core.result.Result;
import com.welove.shop.user.entity.Address;
import com.welove.shop.user.service.AddressService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 内部服务间调用专用 Controller —— 免登录。
 * <p>
 * 路径前缀 {@code /api/internal/**} 全部走白名单,只允许集群内其他微服务通过 Feign 调用。
 * 分层鉴权升级后(Gateway 强校验),网关会拦截外部 /api/internal 请求,内部服务间调用不经网关。
 * <p>
 * 目前暴露:
 * <ul>
 *   <li>GET /api/internal/address/{id} —— trade-service 下单查地址</li>
 * </ul>
 */
@RestController
@RequestMapping("/internal")
@RequiredArgsConstructor
public class InternalAddressController {

    private final AddressService addressService;

    @GetMapping("/address/{id}")
    public Result<Address> getAddress(@PathVariable Long id) {
        Address address = addressService.getById(id);
        if (address == null) {
            throw new BizException(ErrorCode.NOT_FOUND, "地址不存在");
        }
        return Result.ok(address);
    }
}
