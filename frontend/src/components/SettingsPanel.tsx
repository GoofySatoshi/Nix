import React, { useState, useEffect } from 'react';
import { settingsApi, dbConnectionApi, environmentApi, authApi } from '../services/api';

const VENDOR_OPTIONS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'azure', label: 'Azure OpenAI' },
  { value: 'xiaomi', label: '小米 (MiLarge)' },
  { value: 'custom', label: '自定义' },
];

const VENDOR_DEFAULTS: Record<string, { model_list_url: string; api_base_url: string }> = {
  openai: {
    model_list_url: 'https://api.openai.com/v1/models',
    api_base_url: 'https://api.openai.com/v1',
  },
  azure: {
    model_list_url: '',
    api_base_url: '',
  },
  xiaomi: {
    model_list_url: '',
    api_base_url: '',
  },
  custom: {
    model_list_url: '',
    api_base_url: '',
  },
};

const VENDOR_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  azure: 'Azure',
  xiaomi: '小米',
  custom: '自定义',
};

interface KeyConfig {
  id: number;
  name: string;
  vendor: string;
  model_name: string;
  model_list?: string[];
  api_key: string;
  api_base_url: string;
  model_list_url: string;
  is_default: boolean;
  created_at: string;
}

const emptyForm = {
  name: '',
  vendor: 'openai',
  model_name: 'gpt-3.5-turbo',
  model_list: [] as string[],
  api_key: '',
  api_base_url: 'https://api.openai.com/v1',
  model_list_url: 'https://api.openai.com/v1/models',
  is_default: false,
};

const SettingsPanel: React.FC = () => {
  const [configs, setConfigs] = useState<KeyConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // 模态框
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState({ ...emptyForm });
  const [saving, setSaving] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [modelInput, setModelInput] = useState('');

  // 获取模型列表
  const [fetchingModels, setFetchingModels] = useState(false);
  const [fetchedModels, setFetchedModels] = useState<string[]>([]);
  const [showFetchedModels, setShowFetchedModels] = useState(false);

  // 删除确认
  const [deleteId, setDeleteId] = useState<number | null>(null);

  // API Key 显示/隐藏状态
  const [hiddenKeys, setHiddenKeys] = useState<Record<number, boolean>>({});

  // 环境信息状态
  const [envInfo, setEnvInfo] = useState<any>(null);
  const [envLoading, setEnvLoading] = useState(false);
  const [envSaved, setEnvSaved] = useState(false);

  // 用户资料状态
  const [user, setUser] = useState<{ id: number; username: string; email: string; avatar?: string } | null>(null);
  const [showAvatarModal, setShowAvatarModal] = useState(false);
  const [avatarInput, setAvatarInput] = useState('');

  // 数据库连接状态
  const [dbConnections, setDbConnections] = useState<any[]>([]);
  const [showDbModal, setShowDbModal] = useState(false);
  const [editingDbId, setEditingDbId] = useState<number | null>(null);
  const [dbForm, setDbForm] = useState({
    name: '', db_type: 'mysql', host: 'localhost', port: 3306,
    username: '', password: '', database_name: '', extra_params: {}
  });
  const [dbTestResult, setDbTestResult] = useState<{id: number, success: boolean, message: string, latency?: number} | null>(null);
  const [deleteDbId, setDeleteDbId] = useState<number | null>(null);

  useEffect(() => { loadConfigs(); }, []);

  useEffect(() => {
    environmentApi.getInfo().then(info => {
      setEnvInfo(info);
      setEnvSaved(true);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    loadDbConnections();
  }, []);

  useEffect(() => {
    authApi.getProfile().then(data => setUser(data)).catch(() => {});
  }, []);

  const loadConfigs = async () => {
    setLoading(true);
    try {
      const data = await settingsApi.listConfigs();
      setConfigs(data);
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '加载失败' });
    } finally {
      setLoading(false);
    }
  };

  const openCreate = () => {
    setEditingId(null);
    setForm({ ...emptyForm });
    setShowKey(false);
    setFetchedModels([]);
    setShowFetchedModels(false);
    setModelInput('');
    setShowModal(true);
  };

  const openEdit = (cfg: KeyConfig) => {
    setEditingId(cfg.id);
    const ml = cfg.model_list && cfg.model_list.length > 0
      ? cfg.model_list
      : (cfg.model_name ? [cfg.model_name] : []);
    setForm({
      name: cfg.name,
      vendor: cfg.vendor || 'openai',
      model_name: ml[0] || '',
      model_list: ml,
      api_key: '',
      api_base_url: cfg.api_base_url || '',
      model_list_url: cfg.model_list_url || '',
      is_default: cfg.is_default,
    });
    setShowKey(false);
    setFetchedModels([]);
    setShowFetchedModels(false);
    setModelInput('');
    setShowModal(true);
  };

  const handleVendorChange = (vendor: string) => {
    const defaults = VENDOR_DEFAULTS[vendor] || { model_list_url: '', api_base_url: '' };
    setForm(p => ({
      ...p,
      vendor,
      api_base_url: defaults.api_base_url,
      model_list_url: defaults.model_list_url,
    }));
    setFetchedModels([]);
    setShowFetchedModels(false);
  };

  const handleFetchModels = async () => {
    if (!form.model_list_url.trim()) {
      setMessage({ type: 'error', text: '请先填写模型列表地址' });
      return;
    }
    if (!form.api_key.trim()) {
      setMessage({ type: 'error', text: '请先填写 API Key' });
      return;
    }
    setFetchingModels(true);
    setMessage(null);
    try {
      const result = await settingsApi.fetchModels(
        form.model_list_url.trim(),
        form.api_key.trim(),
        form.vendor
      );
      setFetchedModels(result.models);
      setShowFetchedModels(true);
      setMessage({ type: 'success', text: `成功获取 ${result.raw_count} 个模型` });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '获取模型列表失败' });
      setFetchedModels([]);
      setShowFetchedModels(false);
    } finally {
      setFetchingModels(false);
    }
  };

  const handleSave = async () => {
    if (!form.name.trim() || (!editingId && !form.api_key.trim())) return;
    setSaving(true);
    setMessage(null);
    try {
      const payload: any = { ...form };
      payload.model_name = form.model_list?.[0] || form.model_name;
      if (editingId && !payload.api_key.trim()) delete payload.api_key;
      if (editingId) {
        await settingsApi.updateConfig(editingId, payload);
      } else {
        await settingsApi.createConfig(payload);
      }
      setShowModal(false);
      loadConfigs();
      setMessage({ type: 'success', text: editingId ? '配置已更新' : '新配置已创建' });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '保存失败' });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await settingsApi.deleteConfig(deleteId);
      setDeleteId(null);
      loadConfigs();
      setMessage({ type: 'success', text: '配置已删除' });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '删除失败' });
    }
  };

  const handleSetDefault = async (cfg: KeyConfig) => {
    try {
      await settingsApi.updateConfig(cfg.id, { is_default: true });
      loadConfigs();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '设置默认失败' });
    }
  };

  const toggleKeyVisibility = (id: number) => {
    setHiddenKeys(prev => ({ ...prev, [id]: !prev[id] }));
  };

  // ===== 环境信息 =====
  const handleDetectEnvironment = async () => {
    setEnvLoading(true);
    setMessage(null);
    try {
      const info = await environmentApi.detect();
      setEnvInfo(info);
      setEnvSaved(false);
      setMessage({ type: 'success', text: '环境检测完成' });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '环境检测失败' });
    } finally {
      setEnvLoading(false);
    }
  };

  const handleSaveEnvironment = async () => {
    setEnvLoading(true);
    setMessage(null);
    try {
      const info = await environmentApi.save();
      setEnvInfo(info);
      setEnvSaved(true);
      setMessage({ type: 'success', text: '环境信息已保存到项目' });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '保存环境信息失败' });
    } finally {
      setEnvLoading(false);
    }
  };

  // ===== 数据库连接 =====
  const loadDbConnections = async () => {
    try {
      const data = await dbConnectionApi.list();
      setDbConnections(data);
    } catch (err) {}
  };

  const dbTypeDefaults: Record<string, {port: number, needsDb: boolean, needsAuth: boolean}> = {
    mysql: { port: 3306, needsDb: true, needsAuth: true },
    postgresql: { port: 5432, needsDb: true, needsAuth: true },
    redis: { port: 6379, needsDb: false, needsAuth: false },
    elasticsearch: { port: 9200, needsDb: false, needsAuth: false },
    mongodb: { port: 27017, needsDb: true, needsAuth: true },
  };

  const dbTypeLabels: Record<string, string> = {
    mysql: 'MySQL',
    postgresql: 'PostgreSQL',
    redis: 'Redis',
    elasticsearch: 'ElasticSearch',
    mongodb: 'MongoDB',
  };

  const openCreateDb = () => {
    setEditingDbId(null);
    setDbForm({ name: '', db_type: 'mysql', host: 'localhost', port: 3306, username: '', password: '', database_name: '', extra_params: {} });
    setDbTestResult(null);
    setShowDbModal(true);
  };

  const openEditDb = (conn: any) => {
    setEditingDbId(conn.id);
    setDbForm({
      name: conn.name,
      db_type: conn.db_type,
      host: conn.host,
      port: conn.port,
      username: conn.username || '',
      password: '',
      database_name: conn.database_name || '',
      extra_params: conn.extra_params || {},
    });
    setDbTestResult(null);
    setShowDbModal(true);
  };

  const handleDbTypeChange = (dbType: string) => {
    const defaults = dbTypeDefaults[dbType] || { port: 3306, needsDb: true, needsAuth: true };
    setDbForm(p => ({
      ...p,
      db_type: dbType,
      port: defaults.port,
      database_name: defaults.needsDb ? p.database_name : '',
      username: defaults.needsAuth ? p.username : '',
      password: defaults.needsAuth ? p.password : '',
    }));
  };

  const handleDbSave = async () => {
    if (!dbForm.name.trim() || !dbForm.host.trim()) return;
    setMessage(null);
    try {
      const payload = { ...dbForm };
      if (editingDbId) {
        if (!payload.password) delete (payload as any).password;
        await dbConnectionApi.update(editingDbId, payload);
      } else {
        await dbConnectionApi.create(payload);
      }
      setShowDbModal(false);
      loadDbConnections();
      setMessage({ type: 'success', text: editingDbId ? '连接已更新' : '新连接已创建' });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '保存失败' });
    }
  };

  const handleDbDelete = async () => {
    if (!deleteDbId) return;
    try {
      await dbConnectionApi.delete(deleteDbId);
      setDeleteDbId(null);
      loadDbConnections();
      setMessage({ type: 'success', text: '连接已删除' });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '删除失败' });
    }
  };

  const handleDbTest = async (id: number) => {
    setDbTestResult(null);
    try {
      const result = await dbConnectionApi.test(id);
      setDbTestResult({ id, success: result.success, message: result.message, latency: result.latency_ms });
      if (result.success) {
        setMessage({ type: 'success', text: `连接成功，延迟 ${result.latency_ms}ms` });
      } else {
        setMessage({ type: 'error', text: result.message });
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '测试失败' });
    }
  };

  // ===== 加载状态 =====
  if (loading) {
    return (
      <div className="settings-panel">
        <div className="card glass" style={{ display: 'flex', justifyContent: 'center', padding: '60px' }}>
          <span style={{ color: 'var(--text-secondary)' }}>加载中...</span>
        </div>
      </div>
    );
  }

  // ===== 主界面 =====
  return (
    <div className="settings-panel">
      <div className="settings-header">
        <h3>系统设置</h3>
        <p>管理多个 API Key 配置，支持 OpenAI / Azure / 小米 等不同厂商</p>
      </div>

      {/* ===== 用户资料区段 ===== */}
      {user && (
        <div className="card glass" style={{ marginBottom: '32px', padding: '24px', display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div
            style={{ cursor: 'pointer', position: 'relative' }}
            onClick={() => { setAvatarInput(user.avatar || ''); setShowAvatarModal(true); }}
            title="点击更换头像"
          >
            {user.avatar ? (
              <div className="avatar-circle avatar-large">
                <img src={user.avatar} alt={user.username} />
              </div>
            ) : (
              <div className="avatar-circle avatar-large avatar-default">
                <span>{user.username.charAt(0).toUpperCase()}</span>
              </div>
            )}
            <div style={{
              position: 'absolute',
              bottom: 0,
              right: 0,
              width: '24px',
              height: '24px',
              borderRadius: '50%',
              background: 'var(--gradient-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '2px solid var(--glass-bg-strong)'
            }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
                <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
                <circle cx="12" cy="13" r="4"/>
              </svg>
            </div>
          </div>
          <div>
            <div style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--text-primary)' }}>{user.username}</div>
            <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginTop: '2px' }}>{user.email}</div>
          </div>
        </div>
      )}

      {/* ===== 环境信息区段 ===== */}
      <div className="settings-section" style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h4 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>环境信息</h4>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="btn btn-sm btn-secondary" onClick={handleDetectEnvironment} disabled={envLoading}>
              {envLoading ? '检测中...' : '检测环境'}
            </button>
            {envInfo && (
              <button className="btn btn-sm btn-primary" onClick={handleSaveEnvironment} disabled={envLoading || envSaved}>
                {envSaved ? '已保存' : '保存到项目'}
              </button>
            )}
          </div>
        </div>

        {envInfo ? (
          <div className="card glass" style={{ padding: '20px 24px' }}>
            {/* 设备信息 */}
            <div style={{ marginBottom: '16px', paddingBottom: '16px', borderBottom: '1px solid var(--border-color)' }}>
              <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '6px' }}>设备信息</div>
              <div style={{ fontSize: '1rem', fontWeight: 500, color: 'var(--text-primary)' }}>
                {envInfo.device_model || 'Unknown'} | {envInfo.os_name} {envInfo.os_version} | {envInfo.architecture} | {envInfo.shell?.split('/').pop()}
              </div>
            </div>

            {/* 技术栈 */}
            {envInfo.tech_stack && Object.keys(envInfo.tech_stack).length > 0 && (
              <div style={{ marginBottom: '16px', paddingBottom: '16px', borderBottom: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '10px' }}>技术栈</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {Object.entries(envInfo.tech_stack).map(([key, version]: [string, any]) => (
                    <span key={key} className="env-tech-badge">
                      {key} {version}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* 包管理器 */}
            {envInfo.package_managers && envInfo.package_managers.length > 0 && (
              <div style={{ marginBottom: '16px', paddingBottom: '16px', borderBottom: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '10px' }}>可用包管理器</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {envInfo.package_managers.map((pm: string) => (
                    <span key={pm} className="env-pm-badge">{pm}</span>
                  ))}
                </div>
              </div>
            )}

            {/* 终端注意事项 */}
            {envInfo.terminal_notes && envInfo.terminal_notes.length > 0 && (
              <div>
                <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '10px' }}>终端注意事项</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {envInfo.terminal_notes.map((note: string, idx: number) => (
                    <div key={idx} className="env-note-item">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0 }}>
                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
                      </svg>
                      <span>{note}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="card glass" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
            <p style={{ fontSize: '0.9rem', marginBottom: '8px' }}>尚未检测环境信息</p>
            <p style={{ fontSize: '0.8rem' }}>点击"检测环境"按钮获取当前设备信息</p>
          </div>
        )}
      </div>

      {message && (
        <div className={`settings-message ${message.type}`}>
          <span>{message.text}</span>
          <button onClick={() => setMessage(null)} className="settings-message-close">x</button>
        </div>
      )}

      {/* ===== API Key 配置区段 ===== */}
      <div className="settings-section" style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h4 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>API Key 配置</h4>
        </div>

        {/* 添加按钮 */}
        <div style={{ marginBottom: '20px' }}>
          <button className="btn btn-primary" onClick={openCreate}>
            + 添加 Key 配置
          </button>
        </div>

      {/* 配置列表 */}
      {configs.length === 0 ? (
        <div className="card glass" style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
          <p style={{ fontSize: '1rem', marginBottom: '8px' }}>暂无 API Key 配置</p>
          <p>点击上方按钮添加第一个配置</p>
        </div>
      ) : (
        <div className="key-config-list">
          {configs.map(cfg => (
            <div key={cfg.id} className="key-config-card card glass">
              <div className="key-config-main">
                <div className="key-config-info">
                  <div className="key-config-name">
                    {cfg.name}
                    {cfg.is_default && <span className="key-config-badge">默认</span>}
                    <span className="key-config-vendor-badge">{VENDOR_LABELS[cfg.vendor] || cfg.vendor}</span>
                  </div>
                  <div className="key-config-meta">
                    {cfg.model_list && cfg.model_list.length > 0 ? (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {cfg.model_list.map((m, i) => (
                          <span key={i} style={{
                            padding: '2px 8px', fontSize: '11px',
                            background: i === 0 ? 'var(--gradient-primary)' : 'var(--glass-bg)',
                            color: i === 0 ? 'white' : 'var(--text-secondary)',
                            borderRadius: 'var(--radius-badge)',
                            border: i === 0 ? 'none' : '1px solid var(--glass-border)'
                          }}>{m}</span>
                        ))}
                      </div>
                    ) : (
                      <span className="key-config-model">{cfg.model_name}</span>
                    )}
                    {cfg.api_base_url && <span className="key-config-endpoint">{cfg.api_base_url}</span>}
                  </div>
                  <div className="key-config-key" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <code style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {hiddenKeys[cfg.id] ? '••••••••••••' : cfg.api_key}
                    </code>
                    <button
                      className="btn btn-sm btn-secondary"
                      onClick={() => toggleKeyVisibility(cfg.id)}
                      title={hiddenKeys[cfg.id] ? '显示' : '隐藏'}
                      style={{ padding: '4px', flexShrink: 0 }}
                    >
                      {hiddenKeys[cfg.id] ? (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>
                      ) : (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" /><line x1="1" y1="1" x2="23" y2="23" /></svg>
                      )}
                    </button>
                  </div>
                </div>
                <div className="key-config-actions">
                  {!cfg.is_default && (
                    <button className="btn btn-sm btn-secondary" onClick={() => handleSetDefault(cfg)} title="设为默认">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" /></svg>
                    </button>
                  )}
                  <button className="btn btn-sm btn-secondary" onClick={() => openEdit(cfg)}>编辑</button>
                  <button className="btn btn-sm btn-danger" onClick={() => setDeleteId(cfg.id)}>删除</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ===== 创建/编辑模态框 ===== */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '560px' }}>
            <h3>{editingId ? '编辑 Key 配置' : '添加 Key 配置'}</h3>

            <div className="form-group">
              <label className="form-label">配置名称</label>
              <input type="text" className="input" value={form.name}
                onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                placeholder="例如：OpenAI 生产环境、小米测试" />
            </div>

            <div className="form-group">
              <label className="form-label">模型厂商</label>
              <select className="input" value={form.vendor}
                onChange={e => handleVendorChange(e.target.value)}>
                {VENDOR_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">API Key</label>
              <div className="input-with-action">
                <input type={showKey ? 'text' : 'password'} className="input" value={form.api_key}
                  onChange={e => setForm(p => ({ ...p, api_key: e.target.value }))}
                  placeholder={editingId ? '留空则不修改' : 'sk-...'} />
                <button className="btn btn-sm btn-secondary" onClick={() => setShowKey(!showKey)}
                  title={showKey ? '隐藏' : '显示'}>
                  {showKey ? (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" /><line x1="1" y1="1" x2="23" y2="23" /></svg>
                  ) : (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>
                  )}
                </button>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">模型列表接口地址</label>
              <div className="input-with-action">
                <input type="text" className="input" value={form.model_list_url}
                  onChange={e => setForm(p => ({ ...p, model_list_url: e.target.value }))}
                  placeholder="https://api.openai.com/v1/models" />
                <button className="btn btn-sm btn-primary" onClick={handleFetchModels}
                  disabled={fetchingModels || !form.model_list_url.trim() || !form.api_key.trim()}>
                  {fetchingModels ? '获取中...' : '获取模型列表'}
                </button>
              </div>
              <span className="form-hint">填写模型列表接口地址后点击按钮获取可用模型</span>
            </div>

            {/* 获取到的模型列表 */}
            {showFetchedModels && fetchedModels.length > 0 && (
              <div className="form-group fetched-models-box">
                <label className="form-label">
                  可用模型 ({fetchedModels.length})
                </label>
                <div className="fetched-model-list">
                  {fetchedModels.map(m => (
                    <button
                      key={m}
                      type="button"
                      className={`fetched-model-chip ${(form.model_list || []).includes(m) ? 'active' : ''}`}
                      onClick={() => {
                        if ((form.model_list || []).includes(m)) return;
                        const list = [...(form.model_list || []), m];
                        setForm(p => ({ ...p, model_list: list, model_name: list[0] }));
                      }}
                      title="点击添加此模型"
                    >
                      {m}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="form-group">
              <label className="form-label">模型列表</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '8px' }}>
                {(form.model_list || []).map((model, i) => (
                  <span key={i} style={{
                    display: 'inline-flex', alignItems: 'center', gap: '4px',
                    padding: '4px 10px', background: 'var(--glass-bg)',
                    border: '1px solid var(--glass-border)', borderRadius: 'var(--radius-badge)',
                    fontSize: '12px', color: 'var(--text-primary)'
                  }}>
                    {i === 0 && <span style={{ color: 'var(--color-primary-1)', fontSize: '10px' }}>默认</span>}
                    {model}
                    <button onClick={() => {
                      const list = [...(form.model_list || [])];
                      list.splice(i, 1);
                      setForm({...form, model_list: list, model_name: list[0] || ''});
                    }} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: '14px', padding: 0 }}>
                      ×
                    </button>
                  </span>
                ))}
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  value={modelInput}
                  onChange={e => setModelInput(e.target.value)}
                  placeholder="输入模型名称，如 gpt-4o"
                  onKeyDown={e => {
                    if (e.key === 'Enter' && modelInput.trim()) {
                      e.preventDefault();
                      const list = [...(form.model_list || []), modelInput.trim()];
                      setForm({...form, model_list: list, model_name: list[0]});
                      setModelInput('');
                    }
                  }}
                  style={{ flex: 1 }}
                />
                <button className="btn btn-secondary" type="button" onClick={() => {
                  if (modelInput.trim()) {
                    const list = [...(form.model_list || []), modelInput.trim()];
                    setForm({...form, model_list: list, model_name: list[0]});
                    setModelInput('');
                  }
                }}>添加</button>
              </div>
              <span className="form-hint">第一个模型为默认模型，发送消息时默认使用</span>
            </div>

            <div className="form-group">
              <label className="form-label">API Base URL（可选）</label>
              <input type="text" className="input" value={form.api_base_url}
                onChange={e => setForm(p => ({ ...p, api_base_url: e.target.value }))}
                placeholder="https://api.openai.com/v1" />
              <span className="form-hint">调用模型 API 的基础地址，切换厂商时自动填充</span>
            </div>

            <div className="form-group">
              <label className="checkbox-label">
                <input type="checkbox" checked={form.is_default}
                  onChange={e => setForm(p => ({ ...p, is_default: e.target.checked }))} />
                <span>设为默认配置</span>
              </label>
            </div>

            <div className="modal-actions">
              <button className="btn btn-primary" onClick={handleSave}
                disabled={saving || !form.name.trim() || (!editingId && !form.api_key.trim())}>
                {saving ? '保存中...' : '保存'}
              </button>
              <button className="btn btn-secondary" onClick={() => setShowModal(false)}>取消</button>
            </div>
          </div>
        </div>
      )}

      </div>

      {/* ===== 数据库连接区段 ===== */}
      <div className="settings-section" style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h4 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>数据库连接</h4>
        </div>

        <div style={{ marginBottom: '20px' }}>
          <button className="btn btn-primary" onClick={openCreateDb}>
            + 添加连接
          </button>
        </div>

        {dbConnections.length === 0 ? (
          <div className="card glass" style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
            <p style={{ fontSize: '1rem', marginBottom: '8px' }}>暂无数据库连接</p>
            <p>点击上方按钮添加第一个连接</p>
          </div>
        ) : (
          <div className="key-config-list">
            {dbConnections.map(conn => (
              <div key={conn.id} className="key-config-card card glass">
                <div className="key-config-main">
                  <div className="key-config-info">
                    <div className="key-config-name">
                      {conn.name}
                      <span className={`db-type-badge db-type-${conn.db_type}`}>{dbTypeLabels[conn.db_type] || conn.db_type}</span>
                      {dbTestResult && dbTestResult.id === conn.id && (
                        <span className={`status-badge ${dbTestResult.success ? 'success' : 'error'}`} style={{ marginLeft: '8px' }}>
                          {dbTestResult.success ? `已连接 ${dbTestResult.latency}ms` : '连接失败'}
                        </span>
                      )}
                    </div>
                    <div className="key-config-meta">
                      <span className="key-config-model">{conn.host}:{conn.port}</span>
                      {conn.database_name && <span className="key-config-endpoint">{conn.database_name}</span>}
                    </div>
                  </div>
                  <div className="key-config-actions">
                    <button className="btn btn-sm btn-secondary" onClick={() => handleDbTest(conn.id)}>测试</button>
                    <button className="btn btn-sm btn-secondary" onClick={() => openEditDb(conn)}>编辑</button>
                    <button className="btn btn-sm btn-danger" onClick={() => setDeleteDbId(conn.id)}>删除</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ===== Key 删除确认 ===== */}
      {deleteId && (
        <div className="modal-overlay" onClick={() => setDeleteId(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '400px', textAlign: 'center' }}>
            <h3>确认删除</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '20px' }}>确定要删除这个 Key 配置吗？</p>
            <div className="modal-actions" style={{ justifyContent: 'center' }}>
              <button className="btn btn-danger" onClick={handleDelete}>确认删除</button>
              <button className="btn btn-secondary" onClick={() => setDeleteId(null)}>取消</button>
            </div>
          </div>
        </div>
      )}

      {/* ===== 数据库连接创建/编辑模态框 ===== */}
      {showDbModal && (
        <div className="modal-overlay" onClick={() => setShowDbModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '560px' }}>
            <h3>{editingDbId ? '编辑连接' : '添加连接'}</h3>

            <div className="form-group">
              <label className="form-label">连接名称</label>
              <input type="text" className="input" value={dbForm.name}
                onChange={e => setDbForm(p => ({ ...p, name: e.target.value }))}
                placeholder="例如：生产环境 MySQL" />
            </div>

            <div className="form-group">
              <label className="form-label">数据库类型</label>
              <select className="input" value={dbForm.db_type}
                onChange={e => handleDbTypeChange(e.target.value)}>
                <option value="mysql">MySQL</option>
                <option value="postgresql">PostgreSQL</option>
                <option value="redis">Redis</option>
                <option value="elasticsearch">ElasticSearch</option>
                <option value="mongodb">MongoDB</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">主机</label>
              <input type="text" className="input" value={dbForm.host}
                onChange={e => setDbForm(p => ({ ...p, host: e.target.value }))}
                placeholder="localhost" />
            </div>

            <div className="form-group">
              <label className="form-label">端口</label>
              <input type="number" className="input" value={dbForm.port}
                onChange={e => setDbForm(p => ({ ...p, port: parseInt(e.target.value) || 0 }))}
                placeholder="3306" />
            </div>

            {(dbTypeDefaults[dbForm.db_type]?.needsAuth ?? true) && (
              <>
                <div className="form-group">
                  <label className="form-label">用户名</label>
                  <input type="text" className="input" value={dbForm.username}
                    onChange={e => setDbForm(p => ({ ...p, username: e.target.value }))}
                    placeholder="username" />
                </div>
                <div className="form-group">
                  <label className="form-label">密码</label>
                  <input type="password" className="input" value={dbForm.password}
                    onChange={e => setDbForm(p => ({ ...p, password: e.target.value }))}
                    placeholder={editingDbId ? '留空则不修改' : 'password'} />
                </div>
              </>
            )}

            {(dbTypeDefaults[dbForm.db_type]?.needsDb ?? true) && (
              <div className="form-group">
                <label className="form-label">数据库名</label>
                <input type="text" className="input" value={dbForm.database_name}
                  onChange={e => setDbForm(p => ({ ...p, database_name: e.target.value }))}
                  placeholder="database" />
              </div>
            )}

            <div className="modal-actions">
              <button className="btn btn-primary" onClick={handleDbSave}
                disabled={!dbForm.name.trim() || !dbForm.host.trim()}>
                {editingDbId ? '更新' : '创建'}
              </button>
              <button className="btn btn-secondary" onClick={() => setShowDbModal(false)}>取消</button>
            </div>
          </div>
        </div>
      )}

      {/* ===== 数据库连接删除确认 ===== */}
      {deleteDbId && (
        <div className="modal-overlay" onClick={() => setDeleteDbId(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '400px', textAlign: 'center' }}>
            <h3>确认删除</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '20px' }}>确定要删除这个数据库连接吗？</p>
            <div className="modal-actions" style={{ justifyContent: 'center' }}>
              <button className="btn btn-danger" onClick={handleDbDelete}>确认删除</button>
              <button className="btn btn-secondary" onClick={() => setDeleteDbId(null)}>取消</button>
            </div>
          </div>
        </div>
      )}

      {/* ===== 头像更换模态框 ===== */}
      {showAvatarModal && user && (
        <div className="modal-overlay" onClick={() => setShowAvatarModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '420px' }}>
            <h3>更换头像</h3>
            <div className="form-group">
              <label className="form-label">图片链接</label>
              <input
                type="text"
                className="input"
                placeholder="https://example.com/avatar.png"
                value={avatarInput}
                onChange={e => setAvatarInput(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="avatar-upload">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
                <span>点击上传图片</span>
                <input
                  type="file"
                  accept="image/*"
                  onChange={e => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    const reader = new FileReader();
                    reader.onloadend = () => {
                      setAvatarInput(reader.result as string);
                    };
                    reader.readAsDataURL(file);
                  }}
                />
              </label>
            </div>
            {avatarInput && (
              <div className="form-group" style={{ textAlign: 'center' }}>
                <div className="avatar-circle avatar-large">
                  <img src={avatarInput} alt="预览" />
                </div>
              </div>
            )}
            <div className="modal-actions">
              <button
                className="btn btn-primary"
                onClick={async () => {
                  try {
                    const updated = await authApi.updateProfile({ avatar: avatarInput });
                    setUser(updated);
                    setShowAvatarModal(false);
                    setMessage({ type: 'success', text: '头像已更新' });
                  } catch (err: any) {
                    setMessage({ type: 'error', text: err.message || '更新失败' });
                  }
                }}
              >
                保存
              </button>
              <button className="btn btn-secondary" onClick={() => setShowAvatarModal(false)}>取消</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SettingsPanel;
