import { useEffect, useState, useCallback } from 'react';
import { noticeApi } from '../api/admin.js';
import { fmtDateTime, confirmAction, toast, ellipsis } from '../utils/format.js';

const emptyForm = { id: null, title: '', content: '', noticeType: 'SYSTEM', isActive: 1 };

export default function NoticeManagement() {
  const [data, setData] = useState({ records: [], total: 0 });
  const [page, setPage] = useState(1);
  const [size] = useState(10);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(null); // null=不打开, 对象=编辑/新增

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await noticeApi.list({ page, size });
      setData({ records: res?.records || [], total: res?.total || 0 });
    } catch (e) {
      toast(`加载失败: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [page, size]);

  useEffect(() => { load(); }, [load]);

  const submit = async () => {
    if (!editing.title?.trim()) { toast('标题不能为空'); return; }
    if (!editing.content?.trim()) { toast('内容不能为空'); return; }
    try {
      if (editing.id) {
        await noticeApi.update(editing);
      } else {
        await noticeApi.add(editing);
      }
      setEditing(null);
      load();
    } catch (e) {
      toast(`保存失败: ${e.message}`);
    }
  };

  const doDelete = async (n) => {
    if (!confirmAction(`确定删除公告 [${n.title}]？`)) return;
    try {
      await noticeApi.delete(n.id);
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
          <h1 className="page-title">公告管理</h1>
          <div className="page-desc">系统公告 / 活动通知</div>
        </div>
        <button className="btn btn-primary" onClick={() => setEditing({ ...emptyForm })}>+ 新增公告</button>
      </div>

      <div className="table-wrapper">
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>标题</th>
              <th>类型</th>
              <th>状态</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6}><div className="loading-inline">加载中…</div></td></tr>
            ) : data.records.length === 0 ? (
              <tr><td colSpan={6}><div className="empty"><div className="empty-icon">📢</div>暂无公告</div></td></tr>
            ) : data.records.map((n) => (
              <tr key={n.id}>
                <td className="mono">{n.id}</td>
                <td>{ellipsis(n.title, 30)}</td>
                <td><span className="badge badge-info">{n.noticeType || 'SYSTEM'}</span></td>
                <td>
                  {n.isActive === 1
                    ? <span className="badge badge-success">生效中</span>
                    : <span className="badge badge-muted">已关闭</span>}
                </td>
                <td className="text-muted">{fmtDateTime(n.createTime)}</td>
                <td>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button className="btn btn-outline btn-sm" onClick={() => setEditing({ ...n })}>编辑</button>
                    <button className="btn btn-danger btn-sm" onClick={() => doDelete(n)}>删除</button>
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

      {editing && (
        <div className="modal-mask" onClick={(e) => e.target.className === 'modal-mask' && setEditing(null)}>
          <div className="modal">
            <div className="modal-header">
              <h3>{editing.id ? '编辑公告' : '新增公告'}</h3>
              <button className="modal-close" onClick={() => setEditing(null)}>×</button>
            </div>
            <div className="modal-body">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <label>
                  <div className="text-muted" style={{ fontSize: 12, marginBottom: 4 }}>标题</div>
                  <input className="input" value={editing.title || ''} onChange={(e) => setEditing({ ...editing, title: e.target.value })} />
                </label>
                <label>
                  <div className="text-muted" style={{ fontSize: 12, marginBottom: 4 }}>类型</div>
                  <select className="select" value={editing.noticeType || 'SYSTEM'}
                    onChange={(e) => setEditing({ ...editing, noticeType: e.target.value })}>
                    <option value="SYSTEM">系统公告</option>
                    <option value="ACTIVITY">活动通知</option>
                  </select>
                </label>
                <label>
                  <div className="text-muted" style={{ fontSize: 12, marginBottom: 4 }}>内容</div>
                  <textarea className="textarea" style={{ minHeight: 160 }}
                    value={editing.content || ''} onChange={(e) => setEditing({ ...editing, content: e.target.value })} />
                </label>
                <label className="flex-align gap-8">
                  <input type="checkbox" checked={editing.isActive === 1}
                    onChange={(e) => setEditing({ ...editing, isActive: e.target.checked ? 1 : 0 })} />
                  <span>生效</span>
                </label>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setEditing(null)}>取消</button>
              <button className="btn btn-primary" onClick={submit}>保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
