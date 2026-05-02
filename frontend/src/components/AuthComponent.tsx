import React, { useState, useEffect } from 'react';
import { authApi, setAuthToken } from '../services/api';

interface AuthComponentProps {
  onAuthSuccess: (token: string) => void;
  isDarkMode: boolean;
}

const AuthComponent: React.FC<AuthComponentProps> = ({ onAuthSuccess, isDarkMode }) => {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [loginForm, setLoginForm] = useState({ email: '', password: '' });
  const [registerForm, setRegisterForm] = useState({ username: '', email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // 清除错误信息
  useEffect(() => {
    setError('');
  }, [mode]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!loginForm.email || !loginForm.password) {
      setError('请填写邮箱和密码');
      return;
    }

    setLoading(true);
    try {
      const data = await authApi.login(loginForm);
      setAuthToken(data.access_token);
      onAuthSuccess(data.access_token);
    } catch (err: any) {
      setError(err.message || '登录失败，请检查邮箱和密码');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!registerForm.username || !registerForm.email || !registerForm.password) {
      setError('请填写所有字段');
      return;
    }

    if (registerForm.password.length < 6) {
      setError('密码至少需要6个字符');
      return;
    }

    setLoading(true);
    try {
      await authApi.register(registerForm);
      // 注册成功后自动登录
      const data = await authApi.login({
        email: registerForm.email,
        password: registerForm.password,
      });
      setAuthToken(data.access_token);
      onAuthSuccess(data.access_token);
    } catch (err: any) {
      setError(err.message || '注册失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const gradientTitleStyle: React.CSSProperties = {
    fontSize: '1.5rem',
    fontWeight: 700,
    marginBottom: 8,
    background: 'linear-gradient(135deg, var(--color-primary-1), var(--color-primary-2), var(--color-primary-3))',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    backgroundClip: 'text',
  };

  const logoGlowStyle: React.CSSProperties = {
    filter: 'drop-shadow(0 4px 16px rgba(139, 92, 246, 0.35))',
    marginBottom: 16,
  };

  const cardAccentStyle: React.CSSProperties = {
    position: 'absolute',
    top: 0,
    left: '10%',
    right: '10%',
    height: 2,
    background: 'linear-gradient(90deg, transparent, var(--color-primary-1), var(--color-primary-2), var(--color-primary-3), transparent)',
    opacity: 0.6,
    borderRadius: '0 0 2px 2px',
  };

  const orbGlowStyle: React.CSSProperties = {
    position: 'absolute',
    top: '-40px',
    right: '-40px',
    width: 120,
    height: 120,
    borderRadius: '50%',
    background: 'radial-gradient(circle, rgba(139, 92, 246, 0.2) 0%, transparent 70%)',
    pointerEvents: 'none',
    zIndex: 0,
  };

  const orbGlowStyle2: React.CSSProperties = {
    position: 'absolute',
    bottom: '-30px',
    left: '-30px',
    width: 100,
    height: 100,
    borderRadius: '50%',
    background: 'radial-gradient(circle, rgba(6, 182, 212, 0.15) 0%, transparent 70%)',
    pointerEvents: 'none',
    zIndex: 0,
  };

  return (
    <div className="auth-container">
      <div className="auth-card" style={{ position: 'relative', overflow: 'hidden' }}>
        {/* 顶部渐变装饰线 */}
        <div style={cardAccentStyle} />

        {/* 背景光晕装饰 */}
        <div style={orbGlowStyle} />
        <div style={orbGlowStyle2} />

        <div className="auth-header" style={{ position: 'relative', zIndex: 1 }}>
          <div className="auth-logo" style={{ ...logoGlowStyle, fontSize: 'unset', display: 'flex', justifyContent: 'center' }}>
            <svg width="48" height="48" viewBox="0 0 36 36" fill="none">
              <defs>
                <linearGradient id="authLogoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#8B5CF6" />
                  <stop offset="100%" stopColor="#3B82F6" />
                </linearGradient>
              </defs>
              <rect width="36" height="36" rx="10" fill="url(#authLogoGrad)" />
              <path d="M12 24L18 12L24 24H12Z" fill="white" fillOpacity="0.9" />
            </svg>
          </div>
          <h1 style={gradientTitleStyle}>多智能体协作系统</h1>
          <p>登录以管理你的智能体</p>
        </div>

        {/* 切换按钮 */}
        <div className="auth-tabs" style={{ position: 'relative', zIndex: 1 }}>
          <button
            className={`auth-tab ${mode === 'login' ? 'active' : ''}`}
            onClick={() => setMode('login')}
          >
            登录
          </button>
          <button
            className={`auth-tab ${mode === 'register' ? 'active' : ''}`}
            onClick={() => setMode('register')}
          >
            注册
          </button>
        </div>

        {/* 错误提示 */}
        {error && <div className="auth-error" style={{ position: 'relative', zIndex: 1 }}>{error}</div>}

        {/* 登录表单 */}
        {mode === 'login' && (
          <form onSubmit={handleLogin} className="auth-form" style={{ position: 'relative', zIndex: 1 }}>
            <div className="form-group">
              <label className="form-label">邮箱</label>
              <input
                type="email"
                className="input"
                value={loginForm.email}
                onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })}
                placeholder="请输入邮箱"
                autoFocus
              />
            </div>
            <div className="form-group">
              <label className="form-label">密码</label>
              <input
                type="password"
                className="input"
                value={loginForm.password}
                onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                placeholder="请输入密码"
              />
            </div>
            <button
              type="submit"
              className="btn btn-primary auth-submit"
              disabled={loading}
            >
              {loading ? '登录中...' : '登录'}
            </button>
          </form>
        )}

        {/* 注册表单 */}
        {mode === 'register' && (
          <form onSubmit={handleRegister} className="auth-form" style={{ position: 'relative', zIndex: 1 }}>
            <div className="form-group">
              <label className="form-label">用户名</label>
              <input
                type="text"
                className="input"
                value={registerForm.username}
                onChange={(e) => setRegisterForm({ ...registerForm, username: e.target.value })}
                placeholder="请输入用户名"
                autoFocus
              />
            </div>
            <div className="form-group">
              <label className="form-label">邮箱</label>
              <input
                type="email"
                className="input"
                value={registerForm.email}
                onChange={(e) => setRegisterForm({ ...registerForm, email: e.target.value })}
                placeholder="请输入邮箱"
              />
            </div>
            <div className="form-group">
              <label className="form-label">密码</label>
              <input
                type="password"
                className="input"
                value={registerForm.password}
                onChange={(e) => setRegisterForm({ ...registerForm, password: e.target.value })}
                placeholder="请输入密码（至少6位）"
              />
            </div>
            <button
              type="submit"
              className="btn btn-primary auth-submit"
              disabled={loading}
            >
              {loading ? '注册中...' : '注册并登录'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

export default AuthComponent;
