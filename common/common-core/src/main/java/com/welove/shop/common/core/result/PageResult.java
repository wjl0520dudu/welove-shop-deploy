package com.welove.shop.common.core.result;

import java.io.Serial;
import java.io.Serializable;
import java.util.Collections;
import java.util.List;

/**
 * 分页结果。
 * <p>
 * 作为 {@link Result#getData()} 的载荷,而不是替代 Result:
 * <pre>
 * Result&lt;PageResult&lt;Product&gt;&gt; result = Result.ok(pageResult);
 * </pre>
 * 字段与 MyBatis-Plus 的 IPage 兼容:records / total / current / size / pages。
 *
 * @param <T> 单条记录类型
 */
public class PageResult<T> implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    /** 当前页记录。 */
    private List<T> records;

    /** 总记录数。 */
    private long total;

    /** 当前页码(从 1 开始)。 */
    private long current;

    /** 每页大小。 */
    private long size;

    /** 总页数。 */
    private long pages;

    public PageResult() {
    }

    public PageResult(List<T> records, long total, long current, long size) {
        this.records = records == null ? Collections.emptyList() : records;
        this.total = total;
        this.current = current;
        this.size = size;
        this.pages = size == 0 ? 0 : (total + size - 1) / size;
    }

    /** 空分页(常用于查询无结果)。 */
    public static <T> PageResult<T> empty(long current, long size) {
        return new PageResult<>(Collections.emptyList(), 0L, current, size);
    }

    /** 从已知的 records + total 构造(current/size 由调用方给)。 */
    public static <T> PageResult<T> of(List<T> records, long total, long current, long size) {
        return new PageResult<>(records, total, current, size);
    }

    // ---------- getter / setter ----------

    public List<T> getRecords() {
        return records;
    }

    public void setRecords(List<T> records) {
        this.records = records;
    }

    public long getTotal() {
        return total;
    }

    public void setTotal(long total) {
        this.total = total;
    }

    public long getCurrent() {
        return current;
    }

    public void setCurrent(long current) {
        this.current = current;
    }

    public long getSize() {
        return size;
    }

    public void setSize(long size) {
        this.size = size;
    }

    public long getPages() {
        return pages;
    }

    public void setPages(long pages) {
        this.pages = pages;
    }
}
