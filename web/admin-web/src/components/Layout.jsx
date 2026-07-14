import { useNavigate, NavLink, Outlet } from 'react-router-dom';
import './Layout.css';

const MENU = [
  { path: '/dashboard',     icon: '📊', label: '仪表盘' },
  { path: '/users',         icon: '👥', label: '用户管理' },
  { path: '/products',      icon: '🛒', label: '商品管理' },
  { path: '/orders',        icon: '📦', label: '订单管理' },
  { path: '/conversations', icon: '💬', label: '对话管理' },
  // TODO: 以下模块数据源未接入，骨架期先注释，后续增强
  // { path: '/notices',       icon: '📢', label: '公告管理' },
  { path: '/knowledge',     icon: '📚', label: '知识库管理' },
  // { path: '/inspection',    icon: '🔍', label: '知识巡检' },
  // { path: '/agent-runs',    icon: '🤖', label: 'Agent 监控' },
  // { path: '/recommend',     icon: '📈', label: '推荐效果' },
  { path: '/qa-logs',       icon: '📝', label: 'QA 日志' },
];

export default function Layout() {
  const navigate = useNavigate();
  const adminInfoRaw = localStorage.getItem('adminInfo');
  let adminInfo = null;
  try { adminInfo = adminInfoRaw ? JSON.parse(adminInfoRaw) : null; } catch { /* ignore */ }

  const handleLogout = () => {
    localStorage.removeItem('adminToken');
    localStorage.removeItem('adminInfo');
    navigate('/login', { replace: true });
  };

  return (
    <div className="admin-layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-logo">🛍️</span>
          <span className="brand-name">WeLove Shop</span>
        </div>
        <nav className="sidebar-nav">
          {MENU.map((it) => (
            <NavLink
              key={it.path}
              to={it.path}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
            >
              <span className="nav-icon">{it.icon}</span>
              <span className="nav-label">{it.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="admin-info">
            <div className="admin-name">{adminInfo?.username || 'admin'}</div>
            <div className="admin-role">{adminInfo?.role || 'ADMIN'}</div>
          </div>
          <button className="btn btn-outline btn-sm" onClick={handleLogout}>退出登录</button>
        </div>
      </aside>
      <main className="admin-main">
        <Outlet />
      </main>
    </div>
  );
}
