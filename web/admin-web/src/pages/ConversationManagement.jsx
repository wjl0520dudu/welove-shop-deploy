import { useEffect, useState, useCallback } from 'react';
import { conversationApi } from '../api/admin.js';
import { fmtDateTime, confirmAction, toast, ellipsis, buildImageUrl } from '../utils/format.js';

export default function ConversationManagement() {
  const [data, setData] = useState({ records: [], total: 0 });
  const [page, setPage] = useState(1);
  const [size] = useState(20);
  const [filter, setFilter] = useState({ userId: '', keyword: '' });
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [detail, setDetail] = useState(null);
  const [messages, setMessages] = useState([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, size };
      Object.entries(filter).forEach(([k, v]) => { if (v !== '' && v != null) params[k] = v; });
      const res = await conversationApi.list(params);
      setData({ records: res?.records || [], total: res?.total || 0 });
    } catch (e) {
      toast(`加载失败: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [page, size, filter]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { conversationApi.stats().then(setStats).catch(() => {}); }, []);

  const openDetail = async (c) => {
    setDetail(c);
    setMessages([]);
    try {
      const list = await conversationApi.messages(c.id);
      setMessages(list || []);
    } catch (e) {
      toast(`加载消息失败: ${e.message}`);
    }
  };

  const doDelete = async (c) => {
    if (!confirmAction(`确定删除会话 [${c.title || c.id}]？其下所有消息也会删除。`)) return;
    try {
      await conversationApi.delete(c.id);
      load();
    } catch (e) {
      toast(`删除失败: ${e.message}`);
    }
  };

  const totalPages = Math.max(1, Math.ceil(data.total / size));

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">对话管理</h1>
          <div className="page-desc">C 端用户与 AI 的所有会话</div>
        </div>
        {stats && (
          <div className="flex gap-12" style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            <span>会话 <b style={{ color: 'var(--text)' }}>{stats.totalConversations || 0}</b></span>
            <span>消息 <b style={{ color: 'var(--text)' }}>{stats.totalMessages || 0}</b></span>
            <span>今日新增 <b className="text-brand">{stats.todayConversations || 0}</b></span>
          </div>
        )}
      </div>

      <div className="filter-bar">
        <input className="input" style={{ maxWidth: 140 }} placeholder="用户 ID" type="number"
          value={filter.userId} onChange={(e) => setFilter({ ...filter, userId: e.target.value })} />
        <input className="input" placeholder="会话标题" value={filter.keyword}
          onChange={(e) => setFilter({ ...filter, keyword: e.target.value })} />
        <button className="btn btn-primary" onClick={() => (setPage(1), load())}>搜索</button>
      </div>

      <div className="table-wrapper">
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>用户</th>
              <th>标题</th>
              <th>消息数</th>
              <th>更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6}><div className="loading-inline">加载中…</div></td></tr>
            ) : data.records.length === 0 ? (
              <tr><td colSpan={6}><div className="empty"><div className="empty-icon">💬</div>暂无会话</div></td></tr>
            ) : data.records.map((c) => (
              <tr key={c.id}>
                <td className="mono">{c.id}</td>
                <td>{c.userId}</td>
                <td>{ellipsis(c.title, 40) || <span className="text-hint">(无标题)</span>}</td>
                <td>{c.messageCount ?? '-'}</td>
                <td className="text-muted">{fmtDateTime(c.updateTime)}</td>
                <td>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button className="btn btn-outline btn-sm" onClick={() => openDetail(c)}>消息</button>
                    <button className="btn btn-danger btn-sm" onClick={() => doDelete(c)}>删除</button>
                  </div>
                </td>
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

      {detail && (
        <div className="modal-mask" onClick={(e) => e.target.className === 'modal-mask' && setDetail(null)}>
          <div className="modal" style={{ width: 800 }}>
            <div className="modal-header">
              <h3>{detail.title || `会话 #${detail.id}`}</h3>
              <button className="modal-close" onClick={() => setDetail(null)}>×</button>
            </div>
            <div className="modal-body">
              {messages.length === 0 ? (
                <div className="empty"><div className="empty-icon">💭</div>无消息</div>
              ) : messages.map((m) => (
                <div key={m.id} style={{ marginBottom: 12, padding: 12, background: m.role === 'user' ? '#f0fdfa' : '#fff7ed', borderRadius: 8 }}>
                  <div className="flex-between" style={{ marginBottom: 6 }}>
                    <b style={{ color: m.role === 'user' ? 'var(--brand)' : 'var(--accent)' }}>
                      {m.role === 'user' ? '👤 用户' : '🤖 AI'}
                      {m.messageType && m.messageType !== 'text' && <span className="badge badge-muted" style={{ marginLeft: 8 }}>{m.messageType}</span>}
                    </b>
                    <span className="text-hint" style={{ fontSize: 12 }}>{fmtDateTime(m.createTime)}</span>
                  </div>
                  <div style={{ whiteSpace: 'pre-wrap', fontSize: 14, color: 'var(--text)' }}>{m.content || <span className="text-hint">(空)</span>}</div>
                  {m.imageUrl && <img src={buildImageUrl(m.imageUrl)} alt="" style={{ marginTop: 8, maxHeight: 120, borderRadius: 4 }} />}
                </div>
              ))}
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
