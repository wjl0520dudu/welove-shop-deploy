import { useEffect, useState, useCallback } from 'react';
import { orderApi } from '../api/admin.js';
import { fmtDateTime, fmtMoney, ORDER_STATUS, toast, ellipsis } from '../utils/format.js';

export default function OrderManagement() {
  const [data, setData] = useState({ records: [], total: 0 });
  const [page, setPage] = useState(1);
  const [size] = useState(20);
  const [filter, setFilter] = useState({ userId: '', status: '', orderNo: '', keyword: '' });
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [detail, setDetail] = useState(null); // 展开的订单
  const [items, setItems] = useState([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, size };
      Object.entries(filter).forEach(([k, v]) => { if (v !== '' && v != null) params[k] = v; });
      const res = await orderApi.list(params);
      setData({ records: res?.records || [], total: res?.total || 0 });
    } catch (e) {
      toast(`加载失败: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [page, size, filter]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { orderApi.stats().then(setStats).catch(() => {}); }, []);

  const openDetail = async (o) => {
    setDetail(o);
    setItems([]);
    try {
      const list = await orderApi.items(o.id);
      setItems(list || []);
    } catch (e) {
      toast(`加载明细失败: ${e.message}`);
    }
  };

  const totalPages = Math.max(1, Math.ceil(data.total / size));

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">订单管理</h1>
          <div className="page-desc">全部订单 · 明细查看</div>
        </div>
        {stats && (
          <div className="flex gap-12" style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            <span>总数 <b style={{ color: 'var(--text)' }}>{stats.totalOrders || 0}</b></span>
            <span>待付款 <b className="text-warn">{stats.pendingPayment || 0}</b></span>
            <span>待发货 <b className="text-info">{stats.pendingDelivery || 0}</b></span>
            <span>已完成 <b className="text-success">{stats.completed || 0}</b></span>
            <span>营收 <b>{fmtMoney(stats.totalRevenue)}</b></span>
          </div>
        )}
      </div>

      <div className="filter-bar">
        <input className="input" style={{ maxWidth: 120 }} placeholder="用户 ID" type="number"
          value={filter.userId} onChange={(e) => setFilter({ ...filter, userId: e.target.value })} />
        <select className="select" value={filter.status} onChange={(e) => setFilter({ ...filter, status: e.target.value })}>
          <option value="">全部状态</option>
          <option value="0">待付款</option>
          <option value="1">待发货</option>
          <option value="2">待收货</option>
          <option value="3">已完成</option>
          <option value="4">已取消</option>
        </select>
        <input className="input" placeholder="订单号" value={filter.orderNo}
          onChange={(e) => setFilter({ ...filter, orderNo: e.target.value })} />
        <input className="input" placeholder="收货人/手机号" value={filter.keyword}
          onChange={(e) => setFilter({ ...filter, keyword: e.target.value })} />
        <button className="btn btn-primary" onClick={() => (setPage(1), load())}>搜索</button>
      </div>

      <div className="table-wrapper">
        <table className="table">
          <thead>
            <tr>
              <th>订单号</th>
              <th>用户</th>
              <th>收货人</th>
              <th>金额</th>
              <th>状态</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7}><div className="loading-inline">加载中…</div></td></tr>
            ) : data.records.length === 0 ? (
              <tr><td colSpan={7}><div className="empty"><div className="empty-icon">📦</div>暂无订单</div></td></tr>
            ) : data.records.map((o) => {
              const st = ORDER_STATUS[o.status] || { label: o.status, badge: 'badge-muted' };
              return (
                <tr key={o.id}>
                  <td className="mono">{ellipsis(o.orderNo, 20)}</td>
                  <td>{o.userId}</td>
                  <td>{o.receiverName || '-'}<br /><span className="text-muted mono">{o.receiverPhone || ''}</span></td>
                  <td className="text-brand">{fmtMoney(o.payAmount ?? o.totalAmount)}</td>
                  <td><span className={`badge ${st.badge}`}>{st.label}</span></td>
                  <td className="text-muted">{fmtDateTime(o.createTime)}</td>
                  <td><button className="btn btn-outline btn-sm" onClick={() => openDetail(o)}>明细</button></td>
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

      {detail && (
        <div className="modal-mask" onClick={(e) => e.target.className === 'modal-mask' && setDetail(null)}>
          <div className="modal">
            <div className="modal-header">
              <h3>订单明细 · {detail.orderNo}</h3>
              <button className="modal-close" onClick={() => setDetail(null)}>×</button>
            </div>
            <div className="modal-body">
              <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', rowGap: 8, marginBottom: 16 }}>
                <div className="text-muted">用户 ID</div><div>{detail.userId}</div>
                <div className="text-muted">收货人</div><div>{detail.receiverName}</div>
                <div className="text-muted">收货电话</div><div>{detail.receiverPhone}</div>
                <div className="text-muted">收货地址</div><div>{detail.receiverAddress}</div>
                <div className="text-muted">总金额</div><div className="text-brand">{fmtMoney(detail.totalAmount)}</div>
                <div className="text-muted">实付</div><div>{fmtMoney(detail.payAmount)}</div>
                <div className="text-muted">运费</div><div>{fmtMoney(detail.freightAmount)}</div>
                <div className="text-muted">下单</div><div>{fmtDateTime(detail.createTime)}</div>
                {detail.payTime && <><div className="text-muted">支付</div><div>{fmtDateTime(detail.payTime)}</div></>}
                {detail.remark && <><div className="text-muted">备注</div><div>{detail.remark}</div></>}
              </div>
              <div className="text-muted" style={{ marginBottom: 8, fontWeight: 500 }}>商品明细</div>
              <table className="table" style={{ background: '#fafafa', borderRadius: 6 }}>
                <thead><tr><th>商品</th><th>规格</th><th>单价</th><th>数量</th><th>小计</th></tr></thead>
                <tbody>
                  {items.length === 0 ? (
                    <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>无明细</td></tr>
                  ) : items.map((it, i) => (
                    <tr key={i}>
                      <td>{ellipsis(it.productTitle, 30)}</td>
                      <td className="text-muted mono">{it.skuProperties || '-'}</td>
                      <td>{fmtMoney(it.price)}</td>
                      <td>{it.quantity}</td>
                      <td>{fmtMoney(it.totalAmount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
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
