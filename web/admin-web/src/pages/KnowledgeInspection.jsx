import { useState } from 'react';
import { inspectionApi } from '../api/admin.js';
import { toast, ellipsis } from '../utils/format.js';

/**
 * 知识巡检:两个 tab。
 * - unanswered:未命中问题分析(聚类 + 补库建议)
 * - library:库质量分析(重复文档/低质量切片/过期文档)
 */
export default function KnowledgeInspection() {
  const [tab, setTab] = useState('unanswered');
  const [unLoading, setUnLoading] = useState(false);
  const [libLoading, setLibLoading] = useState(false);
  const [unResult, setUnResult] = useState(null);
  const [libResult, setLibResult] = useState(null);
  const [unParams, setUnParams] = useState({ minCount: 1, clusterThreshold: 3 });
  const [libParams, setLibParams] = useState({ minChunkLength: 10, outdatedDays: 180, unaccessedDays: 90, similarityThreshold: 0.8 });

  const runUnanswered = async () => {
    setUnLoading(true);
    try { setUnResult(await inspectionApi.unanswered(unParams)); }
    catch (e) { toast(`分析失败: ${e.message}`); }
    finally { setUnLoading(false); }
  };

  const runLibrary = async () => {
    setLibLoading(true);
    try { setLibResult(await inspectionApi.library(libParams)); }
    catch (e) { toast(`分析失败: ${e.message}`); }
    finally { setLibLoading(false); }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">知识巡检</h1>
          <div className="page-desc">未命中问题分析 + 知识库质量诊断</div>
        </div>
      </div>

      <div className="filter-bar" style={{ padding: 4, background: 'transparent', boxShadow: 'none' }}>
        <button
          className={`btn ${tab === 'unanswered' ? 'btn-primary' : 'btn-outline'}`}
          onClick={() => setTab('unanswered')}
        >未命中问题</button>
        <button
          className={`btn ${tab === 'library' ? 'btn-primary' : 'btn-outline'}`}
          onClick={() => setTab('library')}
        >知识库诊断</button>
      </div>

      {tab === 'unanswered' && (
        <>
          <div className="filter-bar">
            <label className="flex-align gap-8">
              <span className="text-muted" style={{ fontSize: 13 }}>最小出现次数</span>
              <input className="input" style={{ width: 80 }} type="number" min="1" value={unParams.minCount}
                onChange={(e) => setUnParams({ ...unParams, minCount: Number(e.target.value) })} />
            </label>
            <label className="flex-align gap-8">
              <span className="text-muted" style={{ fontSize: 13 }}>聚类阈值</span>
              <input className="input" style={{ width: 80 }} type="number" min="1" value={unParams.clusterThreshold}
                onChange={(e) => setUnParams({ ...unParams, clusterThreshold: Number(e.target.value) })} />
            </label>
            <button className="btn btn-primary" onClick={runUnanswered} disabled={unLoading}>
              {unLoading ? '分析中…' : '开始分析'}
            </button>
          </div>

          {unResult && (
            <div>
              <div className="core-grid" style={{ marginBottom: 20 }}>
                <div className="core-card"><div className="core-body"><div className="core-label">未命中问题总数</div><div className="core-value">{unResult.totalUnansweredCount || 0}</div></div></div>
                <div className="core-card"><div className="core-body"><div className="core-label">去重后问题数</div><div className="core-value">{unResult.totalUniqueQuestions || 0}</div></div></div>
                <div className="core-card"><div className="core-body"><div className="core-label">聚类数</div><div className="core-value">{unResult.clusterCount || 0}</div></div></div>
              </div>

              <div className="card">
                <h3 style={{ margin: '0 0 12px' }}>补库建议</h3>
                {(!unResult.suggestions || unResult.suggestions.length === 0) ? (
                  <div className="empty">暂无建议</div>
                ) : (
                  <table className="table">
                    <thead><tr><th>优先级</th><th>主题</th><th>建议</th><th>问题数</th></tr></thead>
                    <tbody>
                      {unResult.suggestions.map((s, i) => (
                        <tr key={i}>
                          <td>
                            <span className={`badge ${s.priority === '高' ? 'badge-danger' : s.priority === '中' ? 'badge-warn' : 'badge-info'}`}>
                              {s.priority}
                            </span>
                          </td>
                          <td>{s.topic}</td>
                          <td>{s.suggestion}</td>
                          <td>{s.questionCount}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {tab === 'library' && (
        <>
          <div className="filter-bar">
            <label className="flex-align gap-8">
              <span className="text-muted" style={{ fontSize: 13 }}>最小 Chunk 长度</span>
              <input className="input" style={{ width: 80 }} type="number" value={libParams.minChunkLength}
                onChange={(e) => setLibParams({ ...libParams, minChunkLength: Number(e.target.value) })} />
            </label>
            <label className="flex-align gap-8">
              <span className="text-muted" style={{ fontSize: 13 }}>过期天数</span>
              <input className="input" style={{ width: 80 }} type="number" value={libParams.outdatedDays}
                onChange={(e) => setLibParams({ ...libParams, outdatedDays: Number(e.target.value) })} />
            </label>
            <label className="flex-align gap-8">
              <span className="text-muted" style={{ fontSize: 13 }}>相似度阈值</span>
              <input className="input" style={{ width: 80 }} type="number" step="0.05" value={libParams.similarityThreshold}
                onChange={(e) => setLibParams({ ...libParams, similarityThreshold: Number(e.target.value) })} />
            </label>
            <button className="btn btn-primary" onClick={runLibrary} disabled={libLoading}>
              {libLoading ? '分析中…' : '开始诊断'}
            </button>
          </div>

          {libResult && (
            <div>
              <div className="core-grid" style={{ marginBottom: 20 }}>
                <div className="core-card"><div className="core-body"><div className="core-label">文档总数</div><div className="core-value">{libResult.stats?.totalDocs || 0}</div></div></div>
                <div className="core-card"><div className="core-body"><div className="core-label">切片总数</div><div className="core-value">{libResult.stats?.totalChunks || 0}</div></div></div>
                <div className="core-card"><div className="core-body"><div className="core-label">疑似重复组</div><div className="core-value" style={{ color: 'var(--warn)' }}>{libResult.stats?.duplicateDocGroups || 0}</div></div></div>
                <div className="core-card"><div className="core-body"><div className="core-label">低质量切片</div><div className="core-value" style={{ color: 'var(--danger)' }}>{libResult.stats?.lowQualityChunkCount || 0}</div></div></div>
                <div className="core-card"><div className="core-body"><div className="core-label">过期文档</div><div className="core-value" style={{ color: 'var(--warn)' }}>{libResult.stats?.outdatedDocCount || 0}</div></div></div>
              </div>

              {libResult.lowQualityChunks?.length > 0 && (
                <div className="card" style={{ marginBottom: 16 }}>
                  <h3 style={{ margin: '0 0 12px' }}>低质量切片 · {libResult.lowQualityChunks.length}</h3>
                  <table className="table">
                    <thead><tr><th>文档</th><th>切片 #</th><th>问题</th><th>描述</th></tr></thead>
                    <tbody>
                      {libResult.lowQualityChunks.slice(0, 20).map((c, i) => (
                        <tr key={i}>
                          <td>{ellipsis(c.docName, 30)}</td>
                          <td className="mono">{c.chunkIndex}</td>
                          <td><span className="badge badge-warn">{c.issueType}</span></td>
                          <td className="text-muted">{c.issueDescription}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {libResult.outdatedDocs?.length > 0 && (
                <div className="card">
                  <h3 style={{ margin: '0 0 12px' }}>过期文档 · {libResult.outdatedDocs.length}</h3>
                  <table className="table">
                    <thead><tr><th>文档</th><th>距今天数</th></tr></thead>
                    <tbody>
                      {libResult.outdatedDocs.slice(0, 20).map((d, i) => (
                        <tr key={i}>
                          <td>{ellipsis(d.docName, 40)}</td>
                          <td>{d.daySinceUpdate} 天</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
