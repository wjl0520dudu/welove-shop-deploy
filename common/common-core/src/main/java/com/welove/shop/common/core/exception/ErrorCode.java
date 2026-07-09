package com.welove.shop.common.core.exception;

/**
 * 通用错误码。
 * <p>
 * 编码规则:5 位数字,首位区分大类:
 * <ul>
 *   <li>0     — 成功</li>
 *   <li>1xxxx — 通用/系统错误(骨架期只列这一组)</li>
 *   <li>2xxxx — 用户域业务错误(Ph7+ 补,不在本模块)</li>
 *   <li>3xxxx — 商品域业务错误</li>
 *   <li>4xxxx — 交易域业务错误</li>
 *   <li>5xxxx — 对话域业务错误</li>
 *   <li>6xxxx — 管理域业务错误</li>
 * </ul>
 * 业务错误码由各服务在自己的模块里定义,common-core 只留通用错误。
 */
public enum ErrorCode {

    // ---------- 成功 ----------
    SUCCESS(0, "success"),

    // ---------- 通用错误(1xxxx)----------
    /** 入参校验不通过。@Valid / 手工判断都归到这里。 */
    PARAM_INVALID(10001, "参数校验失败"),

    /** 未登录 / token 无效 / token 过期。 */
    UNAUTHORIZED(10002, "未登录或登录已过期"),

    /** 已登录但没权限。 */
    FORBIDDEN(10003, "无权访问"),

    /** 资源不存在。 */
    NOT_FOUND(10004, "资源不存在"),

    /** 通用业务失败。抛 BizException 时不指定 code 就是它。 */
    BIZ_ERROR(10005, "业务处理失败"),

    /** 依赖服务不可用(下游超时/熔断/网络)。 */
    SERVICE_UNAVAILABLE(10006, "服务暂时不可用,请稍后重试"),

    /** 请求过于频繁(限流触发)。 */
    RATE_LIMITED(10007, "请求过于频繁,请稍后再试"),

    /** 内部错误的兜底。GlobalExceptionHandler 捕获未知 Exception 时返回。 */
    INTERNAL_ERROR(10500, "系统内部错误"),
    ;

    private final int code;
    private final String message;

    ErrorCode(int code, String message) {
        this.code = code;
        this.message = message;
    }

    public int getCode() {
        return code;
    }

    public String getMessage() {
        return message;
    }
}
