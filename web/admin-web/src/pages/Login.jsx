import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/admin.js';
import './Login.css';

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    // 已登录直接跳
    if (localStorage.getItem('adminToken')) {
      navigate('/dashboard', { replace: true });
    }
  }, [navigate]);

  const submit = async (e) => {
    e.preventDefault();
    if (!username || !password) {
      setErr('请输入用户名和密码');
      return;
    }
    setErr('');
    setLoading(true);
    try {
      const data = await authApi.login(username.trim(), password);
      // 后端返回 { accessToken, refreshToken, tokenType, admin }
      localStorage.setItem('adminToken', data.accessToken);
      if (data.refreshToken) localStorage.setItem('adminRefreshToken', data.refreshToken);
      if (data.admin) localStorage.setItem('adminInfo', JSON.stringify(data.admin));
      navigate('/dashboard', { replace: true });
    } catch (ex) {
      setErr(ex.message || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <span className="login-logo">🛍️</span>
          <h1>WeLove Shop</h1>
          <p className="login-sub">管理后台</p>
        </div>
        <form onSubmit={submit} className="login-form">
          <label className="login-field">
            <span>用户名</span>
            <input
              className="input"
              type="text"
              value={username}
              autoFocus
              autoComplete="username"
              onChange={(e) => setUsername(e.target.value)}
              disabled={loading}
            />
          </label>
          <label className="login-field">
            <span>密码</span>
            <input
              className="input"
              type="password"
              value={password}
              autoComplete="current-password"
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
            />
          </label>
          {err && <div className="login-err">{err}</div>}
          <button type="submit" className="btn btn-primary btn-lg" disabled={loading}>
            {loading ? '登录中...' : '登 录'}
          </button>
          <p className="login-hint">默认账号 admin / admin123</p>
        </form>
      </div>
    </div>
  );
}
