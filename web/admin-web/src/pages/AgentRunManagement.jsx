import { useEffect, useState, useCallback } from 'react';
import { agentApi } from '../api/admin.js';
import { fmtDateTime, toast, ellipsis } from '../utils/format.js';

export default function AgentRunManagement() {
  const [tab, setTab] = useState('runs');
  const [runs, setRuns] = useState({ records: [], total: 0 });
  const [toolCalls, setToolCalls] = useState({ records: [], total: 0 });
  const [failed, setFailed] = useState([]);
  const [runsFilter, setRunsFilter] = useState({ status: '', userId: '' });
  const [runsPage, setRunsPage] = useState(1);
  const [tcPage, setTcPage] = useState(1);
  const [detail, setDetail] = useState(null);
  const [steps, setSteps] = useState([]);
  const [loading, setLoading] = useState(false);

  const loadRuns = useCallback(async () => {
    setLoading(true);
    try {
      const p = { page: runsPage, size: 20 };
      if (runsFilter.status) p.status = runsFilter.status;
      if (runsFilter.userId) p.userId = runsFilter.userId;
      const res = await agentApi.runs(p);
      setRuns({ records: res?.records || (Array.isArray(res) ? res : []), total: res?.total || 0 });
    } catch (e) { toast(`加载失败: ${e.message}`); }
    finally { setLoading(false); }
  }, [runsPage, runsFilter]);

  const loadToolCalls = useCallback(async () => {
    setLoading(true);
    try {
      const res = await agentApi.toolCalls({ page: tcPage, size: 20 });
      setToolCalls({ records: res?.records || (Array.isArray(res) ? res : []), total: res?.total || 0 });
    } catch (e) { toast(`加载失败: ${e.message}`); }
    finally { setLoading(false); }
  }, [tcPage]);

  const loadFailed = useCallback(async () => {
    try { setFailed(await agentApi.failedToolCalls(20)); }
    catch (e) { toast(`加载失败: ${e.message}`); }
  }, []);

  useEffect(() => {
    if (tab === 'runs') loadRuns();
    else if (tab === 'tool-calls') loadToolCalls();
    else loadFailed();
  }, [tab, loadRuns, loadToolCalls, loadFailed]);

  const openDetail = async (r) => {
    setDetail(r);
    try { setSteps(await agentApi.runSteps(r.runId)); }
    catch (e) { toast(`加载步骤失败: ${e.message}`); setSteps([]); }
  };

  const statusBadge = (s) => {
    switch ((s || '').toLowerCase()) {
      case 'completed': return 'badge-success';
      case 'running':   return 'badge-info';
      case 'failed':    return 'badge-danger';
      case 'cancelled': return 'badge-muted';
      default:          return 'badge-muted';
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Agent 监控</h1>
          <div className="page-desc">运行记录 · 工具调用 · 失败告警</div>
        </div>
      </div>

      <div className="filter-bar" style={{ padding: 4, background: 'transparent', boxShadow: 'none' }}>
        <button className={`btn ${tab === 'runs' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setTab('runs')}>运行记录</button>
        <button className={`btn ${tab === 'tool-calls' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setTab('tool-calls')}>工具调用</button>
        <button className={`btn ${tab === 'failed' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setTab('failed')}>失败调用</button>
      </div>

      {tab === 'runs' && (
        <>
          <div className="filter-bar">
            <select className="select" value={runsFilter.status} onChange={(e) => setRunsFilter({ ...runsFilter, status: e.target.value })}>
              <option value="">全部状态</option>
              <option value="running">running</option>
              <option value="completed">completed</option>
              <option value="failed">failed</option>
              <option value="cancelled">cancelled</option>
            </select>
            <input className="input" placeholder="用户 ID" value={runsFilter.userId}
              onChange={(e) => setRunsFilter({ ...runsFilter, userId: e.target.value })} />
            <button className="btn btn-primary" onClick={() => (setRunsPage(1), loadRuns())}>搜索</button>
          </div>
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Run ID</th>
                  <th>用户</th>
                  <th>意图</th>
                  <th>状态</th>
                  <th>耗时</th>
                  <th>开始时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={7}><div className="loading-inline">加载中…</div></td></tr>
                ) : runs.records.length === 0 ? (
                  <tr><td colSpan={7}><div className="empty"><div className="empty-icon">🤖</div>暂无运行</div></td></tr>
                ) : runs.records.map((r) => (
                  <tr key={r.id || r.runId}>
                    <td className="mono">{ellipsis(r.runId, 12)}</td>
                    <td>{r.userId || '-'}</td>
                    <td>{r.intent || r.goal || '-'}</td>
                    <td><span className={`badge ${statusBadge(r.status)}`}>{r.status}</span></td>
                    <td className="mono">{r.startTime && r.endTime ? `${Math.round((new Date(r.endTime) - new Date(r.startTime)) / 100) / 10}s` : '-'}</td>
                    <td className="text-muted">{fmtDateTime(r.startTime || r.createdAt)}</td>
                    <td><button className="btn btn-outline btn-sm" onClick={() => openDetail(r)}>步骤</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === 'tool-calls' && (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>工具</th>
                <th>Run</th>
                <th>状态</th>
                <th>耗时</th>
                <th>时间</th>
              </tr>
            </thead>
            <tbody>
              {toolCalls.records.map((t) => (
                <tr key={t.id}>
                  <td className="mono">{t.toolName}</td>
                  <td className="mono">{ellipsis(t.runId, 12)}</td>
                  <td><span className={`badge ${statusBadge(t.status)}`}>{t.status}</span></td>
                  <td className="mono">{t.durationMs ? `${t.durationMs} ms` : '-'}</td>
                  <td className="text-muted">{fmtDateTime(t.timestamp || t.createdAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'failed' && (
        <div className="table-wrapper">
          <table className="table">
            <thead><tr><th>工具</th><th>错误</th><th>时间</th></tr></thead>
            <tbody>
              {failed.length === 0 ? (
                <tr><td colSpan={3}><div className="empty"><div className="empty-icon">✅</div>近期无失败</div></td></tr>
              ) : failed.map((t) => (
                <tr key={t.id}>
                  <td className="mono">{t.toolName}</td>
                  <td className="text-danger">{ellipsis(t.errorMessage, 60)}</td>
                  <td className="text-muted">{fmtDateTime(t.timestamp || t.createdAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {detail && (
        <div className="modal-mask" onClick={(e) => e.target.className === 'modal-mask' && setDetail(null)}>
          <div className="modal" style={{ width: 900 }}>
            <div className="modal-header">
              <h3>运行步骤 · {ellipsis(detail.runId, 24)}</h3>
              <button className="modal-close" onClick={() => setDetail(null)}>×</button>
            </div>
            <div className="modal-body">
              {steps.length === 0 ? (
                <div className="empty">暂无步骤</div>
              ) : (
                <table className="table">
                  <thead><tr><th>#</th><th>类型</th><th>名称</th><th>状态</th><th>耗时</th><th>时间</th></tr></thead>
                  <tbody>
                    {steps.map((s, i) => (
                      <tr key={s.id}>
                        <td>{i + 1}</td>
                        <td>{s.stepType || '-'}</td>
                        <td>{s.stepName || '-'}</td>
                        <td><span className={`badge ${statusBadge(s.status)}`}>{s.status}</span></td>
                        <td className="mono">{s.durationMs ? `${s.durationMs} ms` : '-'}</td>
                        <td className="text-muted">{fmtDateTime(s.startTime || s.createdAt)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
