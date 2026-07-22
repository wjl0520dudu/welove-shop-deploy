import { useEffect, useState, useCallback } from 'react';
import { knowledgeApi } from '../api/admin.js';
import { fmtDateTime, confirmAction, toast, ellipsis } from '../utils/format.js';

/**
 * 知识库文档管理。
 * 上传走 chat-service 的 /api/chat/knowledge/upload（admin token 同样有效）。
 * 列表/删除/重试走 admin-bff 聚合。
 */
export default function KnowledgeManagement() {
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadCategory, setUploadCategory] = useState('');

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

  const handleUpload = async () => {
    if (!uploadFile) {
      toast('请选择要上传的 MD 文件');
      return;
    }
    // 检查文件类型
    const name = uploadFile.name || '';
    if (!name.endsWith('.md') && !name.endsWith('.txt')) {
      toast('仅支持 .md 和 .txt 文件');
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      if (uploadCategory) {
        formData.append('categoryId', uploadCategory);
      }
      // 直接上传到 chat-service（admin token 被 chat-service 的 JwtInterceptor 识别为合法 JWT）
      const token = localStorage.getItem('adminToken');
      const resp = await fetch('/api/chat/knowledge/upload', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      const body = await resp.json();
      if (body.code === 0) {
        toast('上传成功，正在解析中…');
        setShowUpload(false);
        setUploadFile(null);
        setUploadCategory('');
        // 延迟刷新，等 ai-service 异步解析完成
        setTimeout(load, 3000);
      } else {
        toast(`上传失败: ${body.message || '未知错误'}`);
      }
    } catch (e) {
      toast(`上传失败: ${e.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleDownloadTemplate = () => {
    // 模板文件在项目 db/data/ 下，直接下载
    const link = document.createElement('a');
    link.href = '/api/chat/knowledge/template';
    link.download = 'knowledge_template.md';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
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
          <div className="page-desc">上传 MD 文档 · 自动切分向量化 · 管理</div>
        </div>
        <div className="flex gap-12">
          <button className="btn btn-outline" onClick={handleDownloadTemplate}>下载模板</button>
          <button className="btn btn-primary" onClick={() => setShowUpload(true)}>+ 上传文档</button>
        </div>
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
              <tr><td colSpan={7}><div className="empty"><div className="empty-icon">📚</div>暂无文档，点击上方"上传文档"添加</div></td></tr>
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

      {showUpload && (
        <div className="modal-mask" onClick={(e) => e.target.className === 'modal-mask' && !uploading && setShowUpload(false)}>
          <div className="modal">
            <div className="modal-header">
              <h3>上传知识文档</h3>
              <button className="modal-close" onClick={() => !uploading && setShowUpload(false)}>×</button>
            </div>
            <div className="modal-body">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div>
                  <div className="text-muted" style={{ fontSize: 12, marginBottom: 4 }}>文件（.md / .txt）</div>
                  <div
                    style={{
                      border: '2px dashed var(--border)',
                      borderRadius: 'var(--radius)',
                      padding: 24,
                      textAlign: 'center',
                      cursor: 'pointer',
                      background: uploadFile ? 'var(--brand-pale)' : 'var(--surface)',
                      borderColor: uploadFile ? 'var(--brand)' : 'var(--border)',
                    }}
                    onClick={() => document.getElementById('file-input').click()}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      const f = e.dataTransfer.files[0];
                      if (f) setUploadFile(f);
                    }}
                  >
                    {uploadFile ? (
                      <div>
                        <div style={{ fontSize: 32, marginBottom: 8 }}>📄</div>
                        <div className="text-brand">{uploadFile.name}</div>
                        <div className="text-hint" style={{ fontSize: 12 }}>{(uploadFile.size / 1024).toFixed(1)} KB</div>
                      </div>
                    ) : (
                      <div>
                        <div style={{ fontSize: 32, marginBottom: 8 }}>📁</div>
                        <div className="text-muted">点击或拖拽文件到此处</div>
                        <div className="text-hint" style={{ fontSize: 12, marginTop: 4 }}>支持 .md / .txt 格式</div>
                      </div>
                    )}
                    <input
                      id="file-input"
                      type="file"
                      accept=".md,.txt"
                      style={{ display: 'none' }}
                      onChange={(e) => setUploadFile(e.target.files[0])}
                    />
                  </div>
                </div>
                <label>
                  <div className="text-muted" style={{ fontSize: 12, marginBottom: 4 }}>分类 ID（可选）</div>
                  <input className="input" type="number" value={uploadCategory} onChange={(e) => setUploadCategory(e.target.value)} placeholder="留空则无分类" />
                </label>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" disabled={uploading} onClick={() => setShowUpload(false)}>取消</button>
              <button className="btn btn-primary" disabled={uploading || !uploadFile} onClick={handleUpload}>
                {uploading ? '上传中…' : '上传并解析'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}