import { useEffect, useState } from 'react';
import { dashboardApi, productApi, orderApi, conversationApi, recommendApi } from '../api/admin.js';
import { fmtMoney } from '../utils/format.js';
import './Dashboard.css';

/**
 * Dashboard —— 顶部 5 张核心卡片 + 下方 3 个模块统计(商品/订单/对话)。
 */
export default function Dashboard() {
  const [core, setCore] = useState({ userCount: 0, productCount: 0, orderCount: 0, conversationCount: 0, todayRevenue: 0 });
  const [productStats, setProductStats] = useState(null);
  const [orderStats, setOrderStats] = useState(null);
  const [convStats, setConvStats] = useState(null);
  const [recommendStats, setRecommendStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      dashboardApi.stats(),
      productApi.stats(),
      orderApi.stats(),
      conversationApi.stats(),
      recommendApi.stats(),
    ]).then(([a, b, c, d, e]) => {
      if (a.status === 'fulfilled' && a.value) setCore(a.value);
      if (b.status === 'fulfilled') setProductStats(b.value);
      if (c.status === 'fulfilled') setOrderStats(c.value);
      if (d.status === 'fulfilled') setConvStats(d.value);
      if (e.status === 'fulfilled') setRecommendStats(e.value);
      setLoading(false);
    });
  }, []);

  const CoreCard = ({ icon, label, value, color }) => (
    <div className="core-card" style={{ borderTop: `3px solid ${color}` }}>
      <div className="core-icon" style={{ background: `${color}22`, color }}>{icon}</div>
      <div className="core-body">
        <div className="core-label">{label}</div>
        <div className="core-value">{value}</div>
      </div>
    </div>
  );

  if (loading) return <div className="page"><div className="loading-inline">加载中…</div></div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">仪表盘</h1>
          <div className="page-desc">系统核心统计概览</div>
        </div>
      </div>

      {/* ===== 5 张核心卡片 ===== */}
      <div className="core-grid">
        <CoreCard icon="👥" label="用户总数"     value={core.userCount || 0}          color="#14b8a6" />
        <CoreCard icon="🛒" label="商品总数"     value={core.productCount || 0}       color="#f97316" />
        <CoreCard icon="📦" label="订单总数"     value={core.orderCount || 0}         color="#3b82f6" />
        <CoreCard icon="💬" label="对话总数"     value={core.conversationCount || 0}  color="#8b5cf6" />
        <CoreCard icon="💰" label="今日营收"     value={fmtMoney(core.todayRevenue)}  color="#10b981" />
      </div>

      {/* ===== 详细统计 3 卡片 ===== */}
      <div className="stat-grid">
        {productStats && (
          <div className="stat-card">
            <div className="stat-title">🛒 商品分布</div>
            <ul className="stat-list">
              <li><span>在售</span><b className="text-success">{productStats.online || 0}</b></li>
              <li><span>下架</span><b className="text-muted">{productStats.offline || 0}</b></li>
              <li><span>合计</span><b>{productStats.total || 0}</b></li>
            </ul>
          </div>
        )}
        {orderStats && (
          <div className="stat-card">
            <div className="stat-title">📦 订单状态</div>
            <ul className="stat-list">
              <li><span>待付款</span><b className="text-warn">{orderStats.pendingPayment || 0}</b></li>
              <li><span>待发货</span><b className="text-info">{orderStats.pendingDelivery || 0}</b></li>
              <li><span>已完成</span><b className="text-success">{orderStats.completed || 0}</b></li>
              <li><span>今日下单</span><b>{orderStats.todayOrders || 0}</b></li>
              <li><span>累计营收</span><b>{fmtMoney(orderStats.totalRevenue)}</b></li>
            </ul>
          </div>
        )}
        {convStats && (
          <div className="stat-card">
            <div className="stat-title">💬 对话统计</div>
            <ul className="stat-list">
              <li><span>会话总数</span><b>{convStats.totalConversations || 0}</b></li>
              <li><span>消息总数</span><b>{convStats.totalMessages || 0}</b></li>
              <li><span>今日新增</span><b className="text-brand">{convStats.todayConversations || 0}</b></li>
            </ul>
          </div>
        )}
        {recommendStats && (
          <div className="stat-card">
            <div className="stat-title">📈 推荐效果</div>
            <ul className="stat-list">
              <li><span>推荐总数</span><b>{recommendStats.totalRecommendations || 0}</b></li>
              <li><span>点击率</span><b className="text-brand">{recommendStats.clickRate || 0}%</b></li>
              <li><span>满意率</span><b className="text-success">{recommendStats.satisfactionRate || 0}%</b></li>
              <li><span>无反馈率</span><b className="text-muted">{recommendStats.noFeedbackRate || 0}%</b></li>
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

/* small color helpers used only inline */

/* text-warn / text-info 补丁 */
