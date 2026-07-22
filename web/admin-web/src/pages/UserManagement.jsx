import { useEffect, useState, useCallback } from 'react';
import { userApi } from '../api/admin.js';
import { fmtDateTime, USER_STATUS, confirmAction, toast } from '../utils/format.js';

export default function UserManagement() {
  const [data, setData] = useState({ records: [], total: 0 });
  const [page, setPage] = useState(1);
  const [size] = useState(10);
  const [keyword, setKeyword] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await userApi.list({ page, size, keyword: keyword || undefined });
      setData({
        records: res?.records || [],
        total: res?.total || 0,
      });
    } catch (e) {
      toast(`加载失败: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [page, size, keyword]);

  useEffect(() => { load(); }, [load]);

  const toggleStatus = async (u) => {
    const next = u.status === 1 ? 0 : 1;
    if (!confirmAction(`确定${next === 0 ? '禁用' : '启用'}用户 ${u.username || u.phone} 吗？`)) return;
    try {
      await userApi.updateStatus(u.id, next);
      load();
    } catch (e) {
      toast(`操作失败: ${e.message}`);
    }
  };

  const totalPages = Math.max(1, Math.ceil(data.total / size));

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">用户管理</h1>
          <div className="page-desc">C 端注册用户列表 · 支持禁用/启用</div>
        </div>
      </div>

      <div className="filter-bar">
        <input
          className="input"
          placeholder="搜索用户名 / 手机号"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && (setPage(1), load())}
        />
        <button className="btn btn-primary" onClick={() => (setPage(1), load())}>搜索</button>
        <button className="btn btn-outline" onClick={() => { setKeyword(''); setPage(1); }}>重置</button>
      </div>

      <div className="table-wrapper">
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>用户名</th>
              <th>手机号</th>
              <th>性别</th>
              <th>年龄段</th>
              <th>状态</th>
              <th>注册时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8}><div className="loading-inline">加载中…</div></td></tr>
            ) : data.records.length === 0 ? (
              <tr><td colSpan={8}><div className="empty"><div className="empty-icon">📭</div>暂无数据</div></td></tr>
            ) : data.records.map((u) => {
              const st = USER_STATUS[u.status] || { label: u.status, badge: 'badge-muted' };
              return (
                <tr key={u.id}>
                  <td className="mono">{u.id}</td>
                  <td>{u.username || '-'}</td>
                  <td>{u.phone || '-'}</td>
                  <td>{u.gender || '-'}</td>
                  <td>{u.ageRange || '-'}</td>
                  <td><span className={`badge ${st.badge}`}>{st.label}</span></td>
                  <td className="text-muted">{fmtDateTime(u.createTime)}</td>
                  <td>
                    <button
                      className={`btn btn-sm ${u.status === 1 ? 'btn-danger' : 'btn-primary'}`}
                      onClick={() => toggleStatus(u)}
                    >
                      {u.status === 1 ? '禁用' : '启用'}
                    </button>
                  </td>
                </tr>
              );
            })}
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
