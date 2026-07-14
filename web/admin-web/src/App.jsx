import { Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import Login from './pages/Login.jsx';
import Layout from './components/Layout.jsx';
import Dashboard from './pages/Dashboard.jsx';
import UserManagement from './pages/UserManagement.jsx';
import ProductManagement from './pages/ProductManagement.jsx';
import OrderManagement from './pages/OrderManagement.jsx';
import ConversationManagement from './pages/ConversationManagement.jsx';
// TODO: 以下模块数据源未接入，骨架期先注释，后续增强
// import NoticeManagement from './pages/NoticeManagement.jsx';
// import KnowledgeManagement from './pages/KnowledgeManagement.jsx';
// import KnowledgeInspection from './pages/KnowledgeInspection.jsx';
// import AgentRunManagement from './pages/AgentRunManagement.jsx';
// import RecommendReport from './pages/RecommendReport.jsx';
import QaLogManagement from './pages/QaLogManagement.jsx';

/** 登录守卫：未登录跳 /login，登录后跳目标页。 */
function RequireAuth() {
  const location = useLocation();
  const token = localStorage.getItem('adminToken');
  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <Outlet />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route element={<RequireAuth />}>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="users" element={<UserManagement />} />
          <Route path="products" element={<ProductManagement />} />
          <Route path="orders" element={<OrderManagement />} />
          <Route path="conversations" element={<ConversationManagement />} />
          {/* TODO: 以下模块数据源未接入，骨架期先注释，后续增强
          <Route path="notices" element={<NoticeManagement />} />
          <Route path="knowledge" element={<KnowledgeManagement />} />
          <Route path="inspection" element={<KnowledgeInspection />} />
          <Route path="agent-runs" element={<AgentRunManagement />} />
          <Route path="recommend" element={<RecommendReport />} />
          */}
          <Route path="qa-logs" element={<QaLogManagement />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
