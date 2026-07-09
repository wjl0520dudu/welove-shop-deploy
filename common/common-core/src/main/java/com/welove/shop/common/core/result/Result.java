package com.welove.shop.common.core.result;

import com.welove.shop.common.core.exception.ErrorCode;

import java.io.Serial;
import java.io.Serializable;

/**
 * 统一响应体。
 * <p>
 * 所有 Controller 返回值都用 Result 包装:
 * <ul>
 *   <li>{@link #ok()}       — 成功、无 data</li>
 *   <li>{@link #ok(Object)} — 成功、带 data</li>
 *   <li>{@link #fail(ErrorCode)}          — 失败,使用枚举默认消息</li>
 *   <li>{@link #fail(int, String)}        — 自定义 code + 消息</li>
 * </ul>
 * 抛 BizException 时不用手动包 Result,GlobalExceptionHandler 会转成 Result。
 *
 * @param <T> data 载荷类型
 */
public class Result<T> implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    /** 错误码,0 表示成功,非 0 表示失败,对齐 ErrorCode.code。 */
    private int code;

    /** 描述信息(成功时为 "success",失败时为具体原因)。 */
    private String message;

    /** 业务载荷。成功时携带,失败时通常为 null。 */
    private T data;

    // ---------- 构造 ----------

    public Result() {
    }

    public Result(int code, String message, T data) {
        this.code = code;
        this.message = message;
        this.data = data;
    }

    // ---------- 快捷工厂 ----------

    /** 成功,无 data。 */
    public static <T> Result<T> ok() {
        return new Result<>(ErrorCode.SUCCESS.getCode(), ErrorCode.SUCCESS.getMessage(), null);
    }

    /** 成功,带 data。 */
    public static <T> Result<T> ok(T data) {
        return new Result<>(ErrorCode.SUCCESS.getCode(), ErrorCode.SUCCESS.getMessage(), data);
    }

    /** 失败,由 ErrorCode 提供 code + 默认消息。 */
    public static <T> Result<T> fail(ErrorCode errorCode) {
        return new Result<>(errorCode.getCode(), errorCode.getMessage(), null);
    }

    /** 失败,由 ErrorCode 提供 code,消息由调用方覆盖(例如带上下文的具体错误)。 */
    public static <T> Result<T> fail(ErrorCode errorCode, String message) {
        return new Result<>(errorCode.getCode(), message, null);
    }

    /** 失败,自定义 code + 消息。业务域自己的错误码走这里。 */
    public static <T> Result<T> fail(int code, String message) {
        return new Result<>(code, message, null);
    }

    // ---------- 判断 ----------

    public boolean isSuccess() {
        return this.code == ErrorCode.SUCCESS.getCode();
    }

    // ---------- getter / setter ----------

    public int getCode() {
        return code;
    }

    public void setCode(int code) {
        this.code = code;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public T getData() {
        return data;
    }

    public void setData(T data) {
        this.data = data;
    }
}
