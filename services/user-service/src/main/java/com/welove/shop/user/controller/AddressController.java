package com.welove.shop.user.controller;

import com.welove.shop.common.core.result.Result;
import com.welove.shop.common.security.context.UserContext;
import com.welove.shop.user.entity.Address;
import com.welove.shop.user.service.AddressService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 收货地址 Controller。
 * <p>
 * userId 全部从 {@link UserContext} 取,拒绝请求体中的越权写入。
 */
@RestController
@RequestMapping("/address")
@RequiredArgsConstructor
public class AddressController {

    private final AddressService addressService;

    @GetMapping("/list")
    public Result<List<Address>> list() {
        return Result.ok(addressService.listByUserId(UserContext.requireUserId()));
    }

    @PostMapping("/add")
    public Result<Address> add(@RequestBody Address address) {
        address.setUserId(UserContext.requireUserId());
        return Result.ok(addressService.addAddress(address));
    }

    @PutMapping("/update")
    public Result<Address> update(@RequestBody Address address) {
        address.setUserId(UserContext.requireUserId());
        return Result.ok(addressService.updateAddress(address));
    }

    @DeleteMapping("/delete")
    public Result<Void> delete(@RequestParam Long id) {
        addressService.deleteAddress(id, UserContext.requireUserId());
        return Result.ok();
    }

    @PutMapping("/setDefault")
    public Result<Void> setDefault(@RequestParam Long id) {
        addressService.setDefault(id, UserContext.requireUserId());
        return Result.ok();
    }
}
