package com.welove.shop.common.web.exception;

import com.welove.shop.common.core.exception.BizException;
import com.welove.shop.common.core.exception.ErrorCode;
import com.welove.shop.common.core.result.Result;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.ConstraintViolationException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.BindException;
import org.springframework.validation.FieldError;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.NoHandlerFoundException;

import java.util.stream.Collectors;

/**
 * 全局异常处理器。
 * <p>
 * 覆盖顺序(粗到细):
 * <ol>
 *   <li>{@link BizException} — 业务异常,按其 code/message 直接返回</li>
 *   <li>@Valid / @Validated 相关的入参校验异常</li>
 *   <li>常见的 Spring MVC 异常(方法不支持 / JSON 解析失败 / 参数缺失 / 类型不匹配 / 404)</li>
 *   <li>兜底 {@link Exception} — 落日志为 ERROR,返回 INTERNAL_ERROR</li>
 * </ol>
 * 默认所有 HTTP 状态码都返回 200,由 Result.code 承担业务成败判断。
 * 需要 HTTP 语义(如 401/403 触发前端刷新 token)时在具体 handler 上加 @ResponseStatus。
 * <p>
 * 通过 {@code common-web} 的自动装配,无需服务自己声明。服务如需定制,可以自己写 @RestControllerAdvice
 * 并加 @Order 覆盖(本类 order=LOWEST_PRECEDENCE)。
 */
@Order(Ordered.LOWEST_PRECEDENCE)
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    // ---------- 业务异常 ----------

    @ExceptionHandler(BizException.class)
    public Result<Void> handleBizException(BizException ex, HttpServletRequest request) {
        log.warn("[BizException] {} {} - code={}, msg={}",
                request.getMethod(), request.getRequestURI(), ex.getCode(), ex.getMessage());
        return Result.fail(ex.getCode(), ex.getMessage());
    }

    // ---------- 入参校验异常(@Valid @RequestBody) ----------

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<Void> handleValidationBody(MethodArgumentNotValidException ex,
                                             HttpServletRequest request) {
        String msg = ex.getBindingResult().getFieldErrors().stream()
                .map(GlobalExceptionHandler::formatFieldError)
                .collect(Collectors.joining("; "));
        log.warn("[Validation] {} {} - {}", request.getMethod(), request.getRequestURI(), msg);
        return Result.fail(ErrorCode.PARAM_INVALID, msg);
    }

    // ---------- 入参校验异常(@Valid 表单/查询) ----------

    @ExceptionHandler(BindException.class)
    public Result<Void> handleBindException(BindException ex, HttpServletRequest request) {
        String msg = ex.getBindingResult().getFieldErrors().stream()
                .map(GlobalExceptionHandler::formatFieldError)
                .collect(Collectors.joining("; "));
        log.warn("[Validation] {} {} - {}", request.getMethod(), request.getRequestURI(), msg);
        return Result.fail(ErrorCode.PARAM_INVALID, msg);
    }

    // ---------- 入参校验异常(@Validated 方法参数) ----------

    @ExceptionHandler(ConstraintViolationException.class)
    public Result<Void> handleConstraintViolation(ConstraintViolationException ex,
                                                  HttpServletRequest request) {
        String msg = ex.getConstraintViolations().stream()
                .map(GlobalExceptionHandler::formatViolation)
                .collect(Collectors.joining("; "));
        log.warn("[Validation] {} {} - {}", request.getMethod(), request.getRequestURI(), msg);
        return Result.fail(ErrorCode.PARAM_INVALID, msg);
    }

    // ---------- Spring MVC 常见异常 ----------

    /** 例:GET 请求命中了 @PostMapping 的接口。 */
    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    public Result<Void> handleMethodNotSupported(HttpRequestMethodNotSupportedException ex,
                                                 HttpServletRequest request) {
        log.warn("[MethodNotSupported] {} {} - {}",
                request.getMethod(), request.getRequestURI(), ex.getMessage());
        return Result.fail(ErrorCode.PARAM_INVALID, "请求方法不支持: " + ex.getMethod());
    }

    /** JSON 无法解析(body 为空或格式错误)。 */
    @ExceptionHandler(HttpMessageNotReadableException.class)
    public Result<Void> handleMessageNotReadable(HttpMessageNotReadableException ex,
                                                 HttpServletRequest request) {
        log.warn("[MessageNotReadable] {} {} - {}",
                request.getMethod(), request.getRequestURI(), ex.getMessage());
        return Result.fail(ErrorCode.PARAM_INVALID, "请求体解析失败");
    }

    /** 必需参数缺失。 */
    @ExceptionHandler(MissingServletRequestParameterException.class)
    public Result<Void> handleMissingParam(MissingServletRequestParameterException ex,
                                           HttpServletRequest request) {
        log.warn("[MissingParam] {} {} - {}",
                request.getMethod(), request.getRequestURI(), ex.getMessage());
        return Result.fail(ErrorCode.PARAM_INVALID, "缺少必要参数: " + ex.getParameterName());
    }

    /** 参数类型不匹配(如 Long 传了 "abc")。 */
    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public Result<Void> handleTypeMismatch(MethodArgumentTypeMismatchException ex,
                                           HttpServletRequest request) {
        log.warn("[TypeMismatch] {} {} - {}",
                request.getMethod(), request.getRequestURI(), ex.getMessage());
        return Result.fail(ErrorCode.PARAM_INVALID, "参数类型错误: " + ex.getName());
    }

    /** URL 找不到对应 handler(未启用 throwExceptionIfNoHandlerFound 时不会到这)。 */
    @ExceptionHandler(NoHandlerFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public Result<Void> handleNoHandler(NoHandlerFoundException ex, HttpServletRequest request) {
        log.warn("[NoHandler] {} {}", request.getMethod(), request.getRequestURI());
        return Result.fail(ErrorCode.NOT_FOUND);
    }

    /**
     * IllegalArgumentException:业务侧手抛的参数校验失败(比如聊天图片超过 10MB、
     * MIME 不在白名单)。语义上等同 400 Bad Request,不当作 500 兜底,让前端能
     * 明确知道是"用户输入问题"而非"服务出错"。
     */
    @ExceptionHandler(IllegalArgumentException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Result<Void> handleIllegalArgument(IllegalArgumentException ex,
                                              HttpServletRequest request) {
        log.warn("[IllegalArgument] {} {} - {}",
                request.getMethod(), request.getRequestURI(), ex.getMessage());
        return Result.fail(ErrorCode.PARAM_INVALID, ex.getMessage());
    }

    // ---------- 兜底 ----------

    @ExceptionHandler(Exception.class)
    public Result<Void> handleException(Exception ex, HttpServletRequest request) {
        log.error("[UnhandledException] {} {}", request.getMethod(), request.getRequestURI(), ex);
        return Result.fail(ErrorCode.INTERNAL_ERROR);
    }

    // ---------- 内部工具 ----------

    private static String formatFieldError(FieldError fieldError) {
        return fieldError.getField() + ": " + fieldError.getDefaultMessage();
    }

    private static String formatViolation(ConstraintViolation<?> violation) {
        String path = violation.getPropertyPath() == null ? "" : violation.getPropertyPath().toString();
        return (path.isEmpty() ? "" : path + ": ") + violation.getMessage();
    }
}
