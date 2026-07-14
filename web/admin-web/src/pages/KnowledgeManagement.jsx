import { useEffect, useState, useCallback } from 'react';
import { knowledgeApi } from '../api/admin.js';
import { fmtDateTime, confirmAction, toast, ellipsis } from '../utils/format.js';

/**
 * 知识库文档管理。
 * 说明:上传接口暂由 C 端已有的 /api/chat/knowledge/upload 承担;
 * admin 页只做列表/删除/重试解析。
 */
export default function KnowledgeManagement() {
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await knowledgeApi.list();
      setList(data || []);
    } catch (e) {
      toast(`加载失败: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const doDelete = async (d) => {
    if (!confirmAction(`确定删除 [${d.docName}]？向量库也会同步删除。`)) return;
    try {
      await knowledgeApi.delete(d.id);
      load();
    } catch (e) {
      toast(`删除失败: ${e.message}`);
    }
  };

  const doRetry = async (d) => {
    if (!confirmAction(`重新解析 [${d.docName}]？`)) return;
    try {
      await knowledgeApi.retryParse(d.id, d.filePath);
      toast('已触发重新解析');
      setTimeout(load, 1500);
    } catch (e) {
      toast(`重试失败: ${e.message}`);
    }
  };

  const statusBadge = (s) => {
    switch (s) {
      case 'COMPLETED':  return 'badge-success';
      case 'PROCESSING': return 'badge-info';
      case 'PENDING':    return 'badge-warn';
      case 'FAILED':     return 'badge-danger';
      default:           return 'badge-muted';
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">知识库管理</h1>
          <div className="page-desc">文档管理 · 状态查看 · 重新解析</div>
        </div>
        <button className="btn btn-outline" onClick={load}>刷新</button>
      </div>

      <div className="table-wrapper">
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>文档名</th>
              <th>类型</th>
              <th>状态</th>
              <th>错误信息</th>
              <th>上传时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7}><div className="loading-inline">加载中…</div></td></tr>
            ) : list.length === 0 ? (
              <tr><td colSpan={7}><div className="empty"><div className="empty-icon">📚</div>暂无文档</div></td></tr>
            ) : list.map((d) => (
              <tr key={d.id}>
                <td className="mono">{d.id}</td>
                <td>{ellipsis(d.docName, 40)}</td>
                <td>{d.docType || '-'}</td>
                <td><span className={`badge ${statusBadge(d.status)}`}>{d.status || '-'}</span></td>
                <td className="text-danger" style={{ maxWidth: 240 }}>{ellipsis(d.errorMessage, 40) || '-'}</td>
                <td className="text-muted">{fmtDateTime(d.createTime)}</td>
                <td>
                  <div style={{ display: 'flex', gap: 4 }}>
                    {d.status === 'FAILED' && (
                      <button className="btn btn-outline btn-sm" onClick={() => doRetry(d)}>重试</button>
                    )}
                    <button className="btn btn-danger btn-sm" onClick={() => doDelete(d)}>删除</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
