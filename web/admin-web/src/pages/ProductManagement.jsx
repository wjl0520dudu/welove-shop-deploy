import { useEffect, useState, useCallback } from 'react';
import { productApi } from '../api/admin.js';
import { fmtMoney, PRODUCT_STATUS, confirmAction, toast, ellipsis, buildImageUrl } from '../utils/format.js';

export default function ProductManagement() {
  const [data, setData] = useState({ records: [], total: 0 });
  const [page, setPage] = useState(1);
  const [size] = useState(20);
  const [filter, setFilter] = useState({
    keyword: '', brand: '', status: '', minPrice: '', maxPrice: '',
    sortBy: 'id', sortOrder: 'desc',
  });
  const [brands, setBrands] = useState([]);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(null);
  const [creating, setCreating] = useState(false);
  const [stats, setStats] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, size };
      Object.entries(filter).forEach(([k, v]) => {
        if (v !== '' && v != null) params[k] = v;
      });
      const res = await productApi.list(params);
      setData({ records: res?.records || [], total: res?.total || 0 });
    } catch (e) {
      toast(`加载失败: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [page, size, filter]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    productApi.brands().then(setBrands).catch(() => {});
    productApi.stats().then(setStats).catch(() => {});
  }, []);

  const toggleStatus = async (p) => {
    const next = p.status === 1 ? 0 : 1;
    if (!confirmAction(`确定${next === 0 ? '下架' : '上架'} 商品 [${p.title}] 吗？`)) return;
    try {
      await productApi.updateStatus(p.id, next);
      load();
    } catch (e) {
      toast(`操作失败: ${e.message}`);
    }
  };

  const submitEdit = async () => {
    if (!editing) return;
    try {
      await productApi.update(editing.id, editing);
      setEditing(null);
      load();
    } catch (e) {
      toast(`保存失败: ${e.message}`);
    }
  };

  const emptyForm = { title: '', brand: '', categoryId: '', basePrice: '', imageUrl: '', description: '', tags: '', status: 1 };

  const submitCreate = async () => {
    if (!editing) return;
    const body = { ...editing };
    if (body.categoryId) body.categoryId = Number(body.categoryId);
    if (body.basePrice) body.basePrice = Number(body.basePrice);
    if (body.status != null) body.status = Number(body.status);
    try {
      await productApi.create(body);
      setEditing(null);
      setCreating(false);
      load();
    } catch (e) {
      toast(`创建失败: ${e.message}`);
    }
  };

  const totalPages = Math.max(1, Math.ceil(data.total / size));

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">商品管理</h1>
          <div className="page-desc">商品列表 · 上下架 · 编辑</div>
        </div>
        {stats && (
          <div className="flex gap-12" style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            <span>总数 <b style={{ color: 'var(--text)' }}>{stats.total || 0}</b></span>
            <span>在售 <b className="text-success">{stats.online || 0}</b></span>
            <span>下架 <b className="text-muted">{stats.offline || 0}</b></span>
          </div>
        )}
      </div>

      <div className="filter-bar">
        <input className="input" placeholder="标题/品牌/标签" value={filter.keyword}
          onChange={(e) => setFilter({ ...filter, keyword: e.target.value })}
          onKeyDown={(e) => e.key === 'Enter' && (setPage(1), load())} />
        <select className="select" value={filter.brand} onChange={(e) => setFilter({ ...filter, brand: e.target.value })}>
          <option value="">全部品牌</option>
          {brands.map((b) => <option key={b} value={b}>{b}</option>)}
        </select>
        <select className="select" value={filter.status} onChange={(e) => setFilter({ ...filter, status: e.target.value })}>
          <option value="">全部状态</option>
          <option value="1">在售</option>
          <option value="0">下架</option>
        </select>
        <input className="input" style={{ maxWidth: 100 }} placeholder="最低价" type="number" value={filter.minPrice}
          onChange={(e) => setFilter({ ...filter, minPrice: e.target.value })} />
        <input className="input" style={{ maxWidth: 100 }} placeholder="最高价" type="number" value={filter.maxPrice}
          onChange={(e) => setFilter({ ...filter, maxPrice: e.target.value })} />
        <select className="select" value={`${filter.sortBy}:${filter.sortOrder}`}
          onChange={(e) => { const [sortBy, sortOrder] = e.target.value.split(':'); setFilter({ ...filter, sortBy, sortOrder }); }}>
          <option value="id:desc">ID 降序</option>
          <option value="base_price:asc">价格升序</option>
          <option value="base_price:desc">价格降序</option>
          <option value="sales_count:desc">销量降序</option>
          <option value="rating:desc">评分降序</option>
        </select>
        <button className="btn btn-primary" onClick={() => (setPage(1), load())}>搜索</button>
        <button className="btn btn-outline" onClick={() => { setEditing({ ...emptyForm }); setCreating(true); }}>+ 新增商品</button>
      </div>

      <div className="table-wrapper">
        <table className="table">
          <thead>
            <tr>
              <th style={{ width: 60 }}>ID</th>
              <th style={{ width: 60 }}>图片</th>
              <th>标题</th>
              <th>品牌</th>
              <th>价格</th>
              <th>销量</th>
              <th>评分</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={9}><div className="loading-inline">加载中…</div></td></tr>
            ) : data.records.length === 0 ? (
              <tr><td colSpan={9}><div className="empty"><div className="empty-icon">📦</div>暂无商品</div></td></tr>
            ) : data.records.map((p) => {
              const st = PRODUCT_STATUS[p.status] || { label: p.status, badge: 'badge-muted' };
              return (
                <tr key={p.id}>
                  <td className="mono">{p.id}</td>
                  <td>
                    {p.imageUrl
                      ? <img src={buildImageUrl(p.imageUrl)} alt="" style={{ width: 40, height: 40, objectFit: 'cover', borderRadius: 4 }} />
                      : <div style={{ width: 40, height: 40, background: '#f1f5f9', borderRadius: 4 }} />}
                  </td>
                  <td>{ellipsis(p.title, 30)}</td>
                  <td>{p.brand || '-'}</td>
                  <td className="text-brand">{fmtMoney(p.basePrice)}</td>
                  <td>{p.salesCount || 0}</td>
                  <td>{p.rating || '-'}</td>
                  <td><span className={`badge ${st.badge}`}>{st.label}</span></td>
                  <td>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button className="btn btn-outline btn-sm" onClick={() => setEditing({ ...p })}>编辑</button>
                      <button
                        className={`btn btn-sm ${p.status === 1 ? 'btn-danger' : 'btn-primary'}`}
                        onClick={() => toggleStatus(p)}
                      >{p.status === 1 ? '下架' : '上架'}</button>
                    </div>
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

      {editing && (
        <div className="modal-mask" onClick={(e) => e.target.className === 'modal-mask' && (setEditing(null), setCreating(false))}>
          <div className="modal">
            <div className="modal-header">
              <h3>{creating ? '新增商品' : `编辑商品 #${editing.id}`}</h3>
              <button className="modal-close" onClick={() => (setEditing(null), setCreating(false))}>×</button>
            </div>
            <div className="modal-body">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <label>
                  <div className="text-muted" style={{ fontSize: 12, marginBottom: 4 }}>标题 *</div>
                  <input className="input" value={editing.title || ''} onChange={(e) => setEditing({ ...editing, title: e.target.value })} placeholder="商品名称" />
                </label>
                <label>
                  <div className="text-muted" style={{ fontSize: 12, marginBottom: 4 }}>品牌</div>
                  <input className="input" value={editing.brand || ''} onChange={(e) => setEditing({ ...editing, brand: e.target.value })} placeholder="品牌名" />
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <label>
                    <div className="text-muted" style={{ fontSize: 12, marginBottom: 4 }}>类目 ID</div>
                    <input className="input" type="number" value={editing.categoryId || ''} onChange={(e) => setEditing({ ...editing, categoryId: e.target.value })} placeholder="1" />
                  </label>
                  <label>
                    <div className="text-muted" style={{ fontSize: 12, marginBottom: 4 }}>价格 *</div>
                    <input className="input" type="number" step="0.01" value={editing.basePrice || ''} onChange={(e) => setEditing({ ...editing, basePrice: e.target.value })} placeholder="99.99" />
                  </label>
                </div>
                <label>
                  <div className="text-muted" style={{ fontSize: 12, marginBottom: 4 }}>主图 URL</div>
                  <input className="input" value={editing.imageUrl || ''} onChange={(e) => setEditing({ ...editing, imageUrl: e.target.value })} placeholder="https://..." />
                </label>
                <label>
                  <div className="text-muted" style={{ fontSize: 12, marginBottom: 4 }}>标签(逗号分隔)</div>
                  <input className="input" value={editing.tags || ''} onChange={(e) => setEditing({ ...editing, tags: e.target.value })} placeholder="洗面奶,氨基酸" />
                </label>
                <label>
                  <div className="text-muted" style={{ fontSize: 12, marginBottom: 4 }}>描述</div>
                  <textarea className="textarea" value={editing.description || ''} onChange={(e) => setEditing({ ...editing, description: e.target.value })} placeholder="商品详细描述" />
                </label>
                {creating && (
                  <label className="flex-align gap-8">
                    <input type="checkbox" checked={editing.status === 1} onChange={(e) => setEditing({ ...editing, status: e.target.checked ? 1 : 0 })} />
                    <span>上架(勾选后立即在售)</span>
                  </label>
                )}
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => (setEditing(null), setCreating(false))}>取消</button>
              <button className="btn btn-primary" onClick={creating ? submitCreate : submitEdit}>
                {creating ? '创建' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
