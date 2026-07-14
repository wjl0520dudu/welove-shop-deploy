import { useEffect, useState, useCallback } from 'react';
import { qaApi } from '../api/admin.js';
import { fmtDateTime, toast, ellipsis } from '../utils/format.js';

export default function QaLogManagement() {
  const [tab, setTab] = useState('logs');
  const [logs, setLogs] = useState({ records: [], total: 0 });
  const [unanswered, setUnanswered] = useState([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState(null);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await qaApi.logs({ page, size: 20 });
      setLogs({ records: res?.records || [], total: res?.total || 0 });
    } catch (e) { toast(`加载失败: ${e.message}`); }
    finally { setLoading(false); }
  }, [page]);

  const loadUn = useCallback(async () => {
    setLoading(true);
    try { setUnanswered(await qaApi.unanswered() || []); }
    catch (e) { toast(`加载失败: ${e.message}`); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    if (tab === 'logs') loadLogs();
    else loadUn();
  }, [tab, loadLogs, loadUn]);

  const totalPages = Math.max(1, Math.ceil(logs.total / 20));

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">QA 日志</h1>
          <div className="page-desc">问答记录 + 未回答问题</div>
        </div>
      </div>

      <div className="filter-bar" style={{ padding: 4, background: 'transparent', boxShadow: 'none' }}>
        <button className={`btn ${tab === 'logs' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setTab('logs')}>问答日志</button>
        <button className={`btn ${tab === 'unanswered' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setTab('unanswered')}>未回答问题</button>
      </div>

      {tab === 'logs' && (
        <>
          <div className="table-wrapper">
            <table className="table">
              <thead><tr><th>ID</th><th>用户</th><th>问题</th><th>任务类型</th><th>耗时</th><th>反馈</th><th>时间</th><th>操作</th></tr></thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={8}><div className="loading-inline">加载中…</div></td></tr>
                ) : logs.records.length === 0 ? (
                  <tr><td colSpan={8}><div className="empty"><div className="empty-icon">📝</div>暂无日志</div></td></tr>
                ) : logs.records.map((l) => (
                  <tr key={l.id}>
                    <td className="mono">{l.id}</td>
                    <td>{l.userId || '-'}</td>
                    <td>{ellipsis(l.question, 40)}</td>
                    <td><span className="badge badge-info">{l.taskType || '-'}</span></td>
                    <td className="mono">{l.durationMs ? `${l.durationMs} ms` : '-'}</td>
                    <td>
                      {l.feedbackType === 'like'    && <span className="badge badge-success">👍</span>}
                      {l.feedbackType === 'dislike' && <span className="badge badge-danger">👎</span>}
                      {!l.feedbackType              && <span className="text-hint">-</span>}
                    </td>
                    <td className="text-muted">{fmtDateTime(l.createTime)}</td>
                    <td><button className="btn btn-outline btn-sm" onClick={() => setDetail(l)}>查看</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="pagination">
              共 {logs.total} 条 · 第 {page} / {totalPages} 页
              <button className="btn btn-outline btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button>
              <button className="btn btn-outline btn-sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>下一页</button>
            </div>
          </div>
        </>
      )}

      {tab === 'unanswered' && (
        <div className="table-wrapper">
          <table className="table">
            <thead><tr><th>问题</th><th>出现次数</th><th>首次记录</th></tr></thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={3}><div className="loading-inline">加载中…</div></td></tr>
              ) : unanswered.length === 0 ? (
                <tr><td colSpan={3}><div className="empty"><div className="empty-icon">✅</div>没有未回答问题</div></td></tr>
              ) : unanswered.map((q) => (
                <tr key={q.id}>
                  <td>{q.question}</td>
                  <td><span className="badge badge-warn">×{q.count}</span></td>
                  <td className="text-muted">{fmtDateTime(q.createTime)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {detail && (
        <div className="modal-mask" onClick={(e) => e.target.className === 'modal-mask' && setDetail(null)}>
          <div className="modal">
            <div className="modal-header">
              <h3>QA 详情 #{detail.id}</h3>
              <button className="modal-close" onClick={() => setDetail(null)}>×</button>
            </div>
            <div className="modal-body">
              <div className="text-muted" style={{ fontSize: 12 }}>问题</div>
              <div style={{ padding: 12, background: '#f0fdfa', borderRadius: 6, marginBottom: 12, whiteSpace: 'pre-wrap' }}>{detail.question}</div>
              <div className="text-muted" style={{ fontSize: 12 }}>回答</div>
              <div style={{ padding: 12, background: '#fff7ed', borderRadius: 6, whiteSpace: 'pre-wrap' }}>{detail.answer || '(无)'}</div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setDetail(null)}>关闭</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
