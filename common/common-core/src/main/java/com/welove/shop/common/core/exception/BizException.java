package com.welove.shop.common.core.exception;

/**
 * 业务异常。
 * <p>
 * 抛出后由 common-web 的 GlobalExceptionHandler 捕获,统一转为 {@code Result} 响应体返回。
 * 业务代码里遇到"违反业务规则"直接 throw,不要 catch 后自己包装 Result。
 *
 * <pre>
 * // 用错误码
 * throw new BizException(ErrorCode.NOT_FOUND);
 *
 * // 用错误码 + 自定义消息(覆盖枚举默认)
 * throw new BizException(ErrorCode.PARAM_INVALID, "手机号格式错误");
 *
 * // 简易用法(默认 BIZ_ERROR)
 * throw new BizException("库存不足");
 * </pre>
 */
public class BizException extends RuntimeException {

    private final int code;

    public BizException(ErrorCode errorCode) {
        super(errorCode.getMessage());
        this.code = errorCode.getCode();
    }

    public BizException(ErrorCode errorCode, String message) {
        super(message);
        this.code = errorCode.getCode();
    }

    public BizException(String message) {
        super(message);
        this.code = ErrorCode.BIZ_ERROR.getCode();
    }

    /** 数值型 code + 消息,给需要自定义业务错误码的场景用。 */
    public BizException(int code, String message) {
        super(message);
        this.code = code;
    }

    public int getCode() {
        return code;
    }
}
