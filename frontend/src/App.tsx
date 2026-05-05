import React, { useState, useEffect } from 'react';
import { Routes, Route, useNavigate, useLocation, Navigate, NavLink } from 'react-router-dom';
import './styles/globals.css';
import './App.css';
import AgentDashboard from './components/AgentDashboard';
import ChatPanel from './components/ChatPanel';
import AIToolbox from './components/AIToolbox';
import SkillsManager from './components/SkillsManager';
import SettingsPanel from './components/SettingsPanel';
import AuthComponent from './components/AuthComponent';
import { ChatProvider } from './context/ChatContext';
import { isAuthenticated as checkAuth, clearAuthToken, toolboxApi } from './services/api';

function App() {
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);
  const [workingDirectory, setWorkingDirectory] = useState<string>('');
  const [isWorkspaceSet, setIsWorkspaceSet] = useState(false);
  const [directories, setDirectories] = useState<{ name: string; path: string; type: string }[]>([]);
  const [currentBrowsePath, setCurrentBrowsePath] = useState('');
  const [parentBrowsePath, setParentBrowsePath] = useState('');
  const [dirLoading, setDirLoading] = useState(false);
  const [dirError, setDirError] = useState('');
  const [showManualInput, setShowManualInput] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  // 初始化主题
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
      setIsDarkMode(savedTheme === 'dark');
    } else {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      setIsDarkMode(prefersDark);
    }
  }, []);

  // 检查登录状态
  useEffect(() => {
    setAuthenticated(checkAuth());
    setAuthChecked(true);
  }, []);

  // 检查工作目录设置
  useEffect(() => {
    const savedDir = localStorage.getItem('chat_working_directory');
    if (savedDir) {
      setWorkingDirectory(savedDir);
      setIsWorkspaceSet(true);
    }
  }, []);

  // 进入目录选择界面时加载默认目录
  useEffect(() => {
    if (authenticated && !isWorkspaceSet) {
      loadDirectories('~');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authenticated, isWorkspaceSet]);

  // 应用主题
  useEffect(() => {
    if (isDarkMode) {
      document.body.className = 'dark';
      localStorage.setItem('theme', 'dark');
    } else {
      document.body.className = 'light';
      localStorage.setItem('theme', 'light');
    }
  }, [isDarkMode]);

  // 认证状态变化时导航
  useEffect(() => {
    if (authChecked) {
      if (!authenticated && location.pathname !== '/login') {
        navigate('/login');
      }
      if (authenticated && location.pathname === '/login') {
        navigate('/agents');
      }
    }
  }, [authenticated, authChecked, location.pathname, navigate]);

  const toggleTheme = () => {
    setIsDarkMode(!isDarkMode);
  };

  const handleLoginSuccess = (token: string) => {
    setAuthenticated(true);
  };

  const handleLogout = () => {
    clearAuthToken();
    setAuthenticated(false);
    navigate('/login');
  };

  const handleSetWorkspace = (dir?: string) => {
    const target = dir || workingDirectory;
    if (target.trim()) {
      localStorage.setItem('chat_working_directory', target.trim());
      setWorkingDirectory(target.trim());
      setIsWorkspaceSet(true);
    }
  };

  const loadDirectories = async (path?: string) => {
    setDirLoading(true);
    setDirError('');
    try {
      const res = await toolboxApi.browseDirectories(path);
      setDirectories(res.directories);
      setCurrentBrowsePath(res.current_path);
      setParentBrowsePath(res.parent_path);
      setWorkingDirectory(res.current_path);
    } catch (e: any) {
      setDirError(e.message || '加载目录失败');
    } finally {
      setDirLoading(false);
    }
  };

  const enterDirectory = (path: string) => {
    loadDirectories(path);
  };

  const goToParent = () => {
    if (parentBrowsePath) {
      loadDirectories(parentBrowsePath);
    }
  };

  const pageTitle: Record<string, string> = {
    '/chat': 'AI 对话',
    '/agents': '智能体管理',
    '/toolbox': 'AI 工具箱',
    '/skills': 'Skills 管理',
    '/settings': '系统设置',
    '/login': '登录',
  };

  const currentTitle = pageTitle[location.pathname] || 'Nix';

  if (!authChecked) {
    return (
      <div className="app" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
        <div style={{ fontSize: '2rem', color: 'var(--text-primary)' }}>加载中...</div>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <div className="app">
        <div className="background-layer">
          <div className="orb orb-1"></div>
          <div className="orb orb-2"></div>
          <div className="orb orb-3"></div>
        </div>
        <Routes>
          <Route path="/login" element={<AuthComponent onAuthSuccess={handleLoginSuccess} isDarkMode={isDarkMode} />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </div>
    );
  }

  return (
    <div className="app">
      {/* 流体渐变背景层 */}
      <div className="background-layer">
        <div className="orb orb-1"></div>
        <div className="orb orb-2"></div>
        <div className="orb orb-3"></div>
      </div>

      {isWorkspaceSet ? (<>
      {/* 毛玻璃侧边栏 */}
      <aside className="sidebar glass">
        <div className="sidebar-header">
          <div className="logo">
            <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
              <defs>
                <linearGradient id="logoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#8B5CF6" />
                  <stop offset="100%" stopColor="#3B82F6" />
                </linearGradient>
              </defs>
              <rect width="36" height="36" rx="10" fill="url(#logoGrad)" />
              <path d="M12 24L18 12L24 24H12Z" fill="white" fillOpacity="0.9" />
            </svg>
          </div>
          <h1>Nix</h1>
          <p>多智能体协作平台</p>
        </div>
        <nav>
          <ul className="nav-menu">
            <li className="nav-item">
              <NavLink to="/chat" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                <span className="nav-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
                    <line x1="8" y1="10" x2="16" y2="10" />
                    <line x1="8" y1="14" x2="13" y2="14" />
                  </svg>
                </span>
                <span>AI 对话</span>
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/agents" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                <span className="nav-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="3" width="7" height="7" />
                    <rect x="14" y="3" width="7" height="7" />
                    <rect x="14" y="14" width="7" height="7" />
                    <rect x="3" y="14" width="7" height="7" />
                  </svg>
                </span>
                <span>智能体管理</span>
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/toolbox" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
                <span className="nav-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
                  </svg>
                </span>
                <span>AI 工具箱</span>
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/skills" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
                <span className="nav-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                  </svg>
                </span>
                <span>Skills</span>
              </NavLink>
            </li>

            <li className="nav-item">
              <NavLink to="/settings" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                <span className="nav-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="3" />
                    <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
                  </svg>
                </span>
                <span>系统设置</span>
              </NavLink>
            </li>
          </ul>
        </nav>
        <div style={{
          padding: '12px 16px', margin: '8px 12px',
          background: 'var(--glass-bg)', borderRadius: 'var(--radius-btn)',
          border: '1px solid var(--glass-border)', fontSize: '12px'
        }}>
          <div style={{ color: 'var(--text-tertiary)', marginBottom: '4px', fontSize: '11px' }}>工作目录</div>
          <div style={{
            color: 'var(--color-primary-2)', fontFamily: "'SF Mono', monospace",
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            fontSize: '11px'
          }} title={workingDirectory}>
            {workingDirectory}
          </div>
          <button onClick={() => { setIsWorkspaceSet(false); }} style={{
            background: 'none', border: 'none', color: 'var(--text-tertiary)',
            cursor: 'pointer', fontSize: '11px', padding: '4px 0 0', textDecoration: 'underline'
          }}>
            切换目录
          </button>
        </div>
      </aside>

      {/* 主内容区 */}
      <div className="main-content">
        <header className="top-bar glass">
          <h2>{currentTitle}</h2>
          <div className="top-bar-actions">
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleLogout}
            >
              登出
            </button>
            <button
              className="theme-toggle"
              onClick={toggleTheme}
              aria-label="切换主题"
            >
              {isDarkMode ? (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="5" />
                  <line x1="12" y1="1" x2="12" y2="3" />
                  <line x1="12" y1="21" x2="12" y2="23" />
                  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                  <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                  <line x1="1" y1="12" x2="3" y2="12" />
                  <line x1="21" y1="12" x2="23" y2="12" />
                  <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                  <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                </svg>
              ) : (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
                </svg>
              )}
            </button>
          </div>
        </header>
        <main className="content">
          <ChatProvider>
            <Routes>
              <Route path="/" element={<Navigate to="/chat" replace />} />
              <Route path="/chat" element={<ChatPanel />} />
              <Route path="/agents" element={<AgentDashboard />} />
              <Route path="/toolbox" element={<AIToolbox />} />
              <Route path="/skills" element={<SkillsManager />} />
              <Route path="/settings" element={<SettingsPanel />} />
              <Route path="/login" element={<Navigate to="/chat" replace />} />
            </Routes>
          </ChatProvider>
        </main>
      </div>
    </>) : (
      <div className="workspace-gate">
        <div className="workspace-gate-card glass">
          <div className="workspace-gate-header">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary-1)" strokeWidth="1.5">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
            <h2>选择工作目录</h2>
            <p>请选择一个目录作为工作空间。AI 的文件操作将限制在此目录范围内。</p>
          </div>

          {/* 面包屑路径 */}
          <div className="dir-breadcrumb">
            {currentBrowsePath.split('/').filter(Boolean).map((segment, idx, arr) => {
              const path = '/' + arr.slice(0, idx + 1).join('/');
              return (
                <React.Fragment key={idx}>
                  <span className="dir-breadcrumb-sep">/</span>
                  <span className="dir-breadcrumb-item" onClick={() => enterDirectory(path)}>
                    {segment}
                  </span>
                </React.Fragment>
              );
            })}
            {!currentBrowsePath.split('/').filter(Boolean).length && (
              <span className="dir-breadcrumb-item">/</span>
            )}
          </div>

          {/* 目录列表 */}
          <div className="dir-list">
            {dirLoading ? (
              <div className="dir-list-loading">加载中...</div>
            ) : dirError ? (
              <div className="dir-list-error">{dirError}</div>
            ) : directories.length === 0 ? (
              <div className="dir-list-empty">此目录下没有子目录</div>
            ) : (
              directories.map((dir) => (
                <div
                  key={dir.path}
                  className="dir-list-item"
                  onClick={() => enterDirectory(dir.path)}
                  title={dir.path}
                >
                  <span className="dir-list-icon">📁</span>
                  <span className="dir-list-name">{dir.name}</span>
                </div>
              ))
            )}
          </div>

          {/* 底部操作栏 */}
          <div className="dir-actions">
            <div className="dir-actions-info">
              <span>当前选择: </span>
              <code>{currentBrowsePath || workingDirectory || '~'}</code>
            </div>
            <div className="dir-actions-btns">
              <button
                className="btn btn-secondary btn-sm"
                onClick={goToParent}
                disabled={!parentBrowsePath || dirLoading}
              >
                返回上级
              </button>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => handleSetWorkspace(currentBrowsePath)}
                disabled={!currentBrowsePath || dirLoading}
              >
                选择此目录
              </button>
            </div>
          </div>

          {/* 手动输入折叠 */}
          <div className="dir-manual-toggle">
            <button className="dir-manual-toggle-btn" onClick={() => setShowManualInput(!showManualInput)}>
              {showManualInput ? '隐藏手动输入' : '手动输入路径'}
            </button>
            {showManualInput && (
              <div className="dir-manual-input">
                <input
                  type="text"
                  value={workingDirectory}
                  onChange={e => setWorkingDirectory(e.target.value)}
                  placeholder="/path/to/your/project"
                  onKeyDown={e => e.key === 'Enter' && handleSetWorkspace()}
                />
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => handleSetWorkspace()}
                  disabled={!workingDirectory.trim()}
                >
                  进入系统
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    )}
    </div>
  );
}

export default App;
