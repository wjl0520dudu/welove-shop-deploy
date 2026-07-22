import { useEffect, useState, useCallback } from 'react';
import { recommendApi } from '../api/admin.js';
import { fmtDateTime, toast, ellipsis } from '../utils/format.js';

export default function RecommendReport() {
  const [stats, setStats] = useState(null);
  const [data, setData] = useState({ records: [], total: 0 });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await recommendApi.logs({ page, size: 20 });
      setData({ records: res?.records || [], total: res?.total || 0 });
    } catch (e) { toast(`加载失败: ${e.message}`); }
    finally { setLoading(false); }
  }, [page]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { recommendApi.stats().then(setStats).catch(() => {}); }, []);

  const totalPages = Math.max(1, Math.ceil(data.total / 20));

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">推荐效果</h1>
          <div className="page-desc">AI 商品推荐日志 · 点击率 / 满意度</div>
        </div>
      </div>

      {stats && (
        <div className="core-grid" style={{ marginBottom: 20 }}>
          <div className="core-card"><div className="core-body"><div className="core-label">推荐总数</div><div className="core-value">{stats.totalRecommendations || 0}</div></div></div>
          <div className="core-card"><div className="core-body"><div className="core-label">点击率</div><div className="core-value" style={{ color: 'var(--brand)' }}>{stats.clickRate || 0}%</div></div></div>
          <div className="core-card"><div className="core-body"><div className="core-label">满意率</div><div className="core-value" style={{ color: 'var(--success)' }}>{stats.satisfactionRate || 0}%</div></div></div>
          <div className="core-card"><div className="core-body"><div className="core-label">无反馈率</div><div className="core-value" style={{ color: 'var(--text-muted)' }}>{stats.noFeedbackRate || 0}%</div></div></div>
        </div>
      )}

      <div className="table-wrapper">
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>用户</th>
              <th>Query</th>
              <th>意图</th>
              <th>推荐商品数</th>
              <th>点击</th>
              <th>反馈</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8}><div className="loading-inline">加载中…</div></td></tr>
            ) : data.records.length === 0 ? (
              <tr><td colSpan={8}><div className="empty"><div className="empty-icon">📈</div>暂无日志</div></td></tr>
            ) : data.records.map((r) => (
              <tr key={r.id}>
                <td className="mono">{r.id}</td>
                <td>{r.userId || '-'}</td>
                <td>{ellipsis(r.query, 40)}</td>
                <td>{r.intent || '-'}</td>
                <td>{r.recommendedProductIds?.length || 0}</td>
                <td>
                  {r.userClicked === 1
                    ? <span className="badge badge-success">是</span>
                    : <span className="badge badge-muted">否</span>}
                </td>
                <td>
                  {r.userFeedback === 1 && <span className="badge badge-success">满意</span>}
                  {r.userFeedback === 0 && <span className="badge badge-danger">不满意</span>}
                  {r.userFeedback == null && <span className="text-hint">-</span>}
                </td>
                <td className="text-muted">{fmtDateTime(r.createTime)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="pagination">
          共 {data.total} 条 · 第 {page} / {totalPages} 页
          <button className="btn btn-outline btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button>
          <button className="btn btn-outline btn-sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>下一页</button>
        </div>
      </div>
    </div>
  );
}
