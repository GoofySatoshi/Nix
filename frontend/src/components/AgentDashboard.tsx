import React, { useState, useEffect } from 'react';
import { agentApi, settingsApi } from '../services/api';

interface Agent {
  id: number;
  name: string;
  type: string;
  personality: string;
  status: string;
  config_id?: number | null;
  config_name?: string;
  avatar?: string;
  created_at: string;
  updated_at: string;
}

const AgentDashboard: React.FC = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [agentTypes, setAgentTypes] = useState<string[]>([]);
  const [typesLoading, setTypesLoading] = useState(true);

  // 编辑智能体状态
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);
  const [editForm, setEditForm] = useState<{
    name: string;
    personality: string;
    config_id: number | null;
    avatar: string;
  }>({
    name: '',
    personality: '',
    config_id: null,
    avatar: ''
  });

  // 添加智能体状态
  const [showAddModal, setShowAddModal] = useState(false);
  const [addForm, setAddForm] = useState<{
    name: string;
    type: string;
    customType: string;
    personality: string;
    config_id: number | null;
    avatar: string;
  }>({
    name: '',
    type: 'general',
    customType: '',
    personality: '',
    config_id: null,
    avatar: ''
  });
  const [useCustomType, setUseCustomType] = useState(false);

  // 可用AI模型列表
  const [availableModels, setAvailableModels] = useState<any[]>([]);

  // 调度面板状态
  const [showSchedulePanel, setShowSchedulePanel] = useState(false);
  const [dispatchForm, setDispatchForm] = useState({
    source_agent_id: '',
    target_agent_id: '',
    task_name: '',
    task_description: '',
    priority: '1'
  });
  const [autoScheduleForm, setAutoScheduleForm] = useState({
    task_name: '',
    task_description: '',
    preferred_agent_type: '',
    priority: '1'
  });
  const [availableScheduleAgents, setAvailableScheduleAgents] = useState<any[]>([]);
  const [scheduleResult, setScheduleResult] = useState<string | null>(null);
  const [scheduleLoading, setScheduleLoading] = useState(false);

  useEffect(() => {
    // 模拟获取智能体列表
    const fetchAgents = async () => {
      try {
        const data = await agentApi.getAgents();
        setAgents(data);
      } catch (error) {
        console.error('Error fetching agents:', error);
        // 模拟数据
        setAgents([
          {
            id: 1,
            name: '智能助手',
            type: 'general',
            personality: '友好、乐于助人，善于解答各种问题，语气亲切自然。',
            status: 'running',
            created_at: '2026-04-10T10:00:00',
            updated_at: '2026-04-10T10:00:00'
          },
          {
            id: 2,
            name: '数据分析专家',
            type: 'data_analyst',
            personality: '严谨、专业，注重数据准确性，分析问题深入细致。',
            status: 'stopped',
            created_at: '2026-04-10T11:00:00',
            updated_at: '2026-04-10T11:00:00'
          },
          {
            id: 3,
            name: '代码生成器',
            type: 'code_generator',
            personality: '高效、精确，擅长编写高质量代码，注重代码可读性和性能。',
            status: 'running',
            created_at: '2026-04-10T12:00:00',
            updated_at: '2026-04-10T12:00:00'
          }
        ]);
      } finally {
        setLoading(false);
      }
    };

    fetchAgents();
  }, []);

  // 获取可用AI模型列表
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const data = await settingsApi.listConfigs();
        setAvailableModels(data);
      } catch (error) {
        console.error('Error fetching models:', error);
      }
    };

    fetchModels();
  }, []);

  // 获取智能体类型
  useEffect(() => {
    const fetchAgentTypes = async () => {
      try {
        const data = await agentApi.getAgentTypes();
        setAgentTypes(data.types);
      } catch (error) {
        console.error('Error fetching agent types:', error);
        // 模拟数据
        setAgentTypes(['general', 'data_analyst', 'code_generator']);
      } finally {
        setTypesLoading(false);
      }
    };

    fetchAgentTypes();
  }, []);

  const handleStartAgent = async (agentId: number) => {
    try {
      await agentApi.startAgent(agentId);
      // 刷新智能体列表
      const data = await agentApi.getAgents();
      setAgents(data);
    } catch (error) {
      console.error('Error starting agent:', error);
      // 模拟更新
      setAgents(agents.map(agent =>
        agent.id === agentId ? { ...agent, status: 'running' } : agent
      ));
    }
  };

  const handleStopAgent = async (agentId: number) => {
    try {
      await agentApi.stopAgent(agentId);
      // 刷新智能体列表
      const data = await agentApi.getAgents();
      setAgents(data);
    } catch (error) {
      console.error('Error stopping agent:', error);
      // 模拟更新
      setAgents(agents.map(agent =>
        agent.id === agentId ? { ...agent, status: 'stopped' } : agent
      ));
    }
  };

  if (loading) {
    return (
      <div className="agent-dashboard">
        <div className="card" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '60px', minHeight: '300px' }}>
          <span style={{ fontSize: '1.125rem', color: 'var(--text-secondary)', animation: 'pulse 2s infinite' }}>
            正在加载智能体列表...
          </span>
        </div>
      </div>
    );
  }

  const handleEditAgent = (agent: Agent) => {
    setEditingAgent(agent);
    setEditForm({
      name: agent.name,
      personality: agent.personality || '',
      config_id: agent.config_id ?? null,
      avatar: agent.avatar || ''
    });
  };

  const handleSaveAgent = async () => {
    if (!editingAgent) return;

    try {
      const updatedAgent = await agentApi.updateAgent(editingAgent.id, editForm);
      setAgents(agents.map(agent =>
        agent.id === editingAgent.id ? updatedAgent : agent
      ));
      setEditingAgent(null);
    } catch (error) {
      console.error('Error updating agent:', error);
      // 模拟更新
      setAgents(agents.map(agent =>
        agent.id === editingAgent.id ? { ...agent, ...editForm, updated_at: new Date().toISOString() } : agent
      ));
      setEditingAgent(null);
    }
  };

  const handleCancelEdit = () => {
    setEditingAgent(null);
    setEditForm({ name: '', personality: '', config_id: null, avatar: '' });
  };

  const handleAddAgent = () => {
    setShowAddModal(true);
  };

  // 头像工具函数
  const AVATAR_COLORS = [
    '#8b5cf6', '#3b82f6', '#06b6d4', '#10b981', '#f59e0b',
    '#ef4444', '#ec4899', '#6366f1', '#14b8a6', '#f97316'
  ];

  const getDefaultAvatar = (name: string, seed?: number) => {
    const idx = (seed ?? name.charCodeAt(0)) % AVATAR_COLORS.length;
    const color = AVATAR_COLORS[idx];
    const initial = name.charAt(0).toUpperCase() || 'A';
    return `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" rx="32" fill="${encodeURIComponent(color)}"/><text x="32" y="38" text-anchor="middle" fill="white" font-size="28" font-family="system-ui, sans-serif" font-weight="600">${initial}</text></svg>`;
  };

  const AvatarImage: React.FC<{ agent: Agent; size?: 'small' | 'medium' }> = ({ agent, size = 'medium' }) => {
    const sizeClass = size === 'small' ? 'avatar-small' : 'avatar-medium';
    if (agent.avatar) {
      return (
        <div className={`avatar-circle ${sizeClass}`}>
          <img src={agent.avatar} alt={agent.name} />
        </div>
      );
    }
    return (
      <div className={`avatar-circle ${sizeClass} avatar-default`}>
        <span>{agent.name.charAt(0).toUpperCase()}</span>
      </div>
    );
  };

  const AvatarPicker: React.FC<{
    value: string;
    name: string;
    onChange: (value: string) => void;
  }> = ({ value, name, onChange }) => {
    const [tab, setTab] = useState<'preset' | 'url' | 'upload'>('preset');
    const [urlInput, setUrlInput] = useState(value.startsWith('http') ? value : '');

    const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onloadend = () => {
        onChange(reader.result as string);
      };
      reader.readAsDataURL(file);
    };

    return (
      <div>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
          {(['preset', 'url', 'upload'] as const).map(t => (
            <button
              key={t}
              type="button"
              className={`btn btn-sm ${tab === t ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setTab(t)}
            >
              {t === 'preset' ? '预设' : t === 'url' ? '链接' : '上传'}
            </button>
          ))}
        </div>
        {tab === 'preset' && (
          <div className="avatar-picker-grid">
            {AVATAR_COLORS.map((color, i) => {
              const svg = getDefaultAvatar(name || 'A', i);
              return (
                <div
                  key={color}
                  className={`avatar-picker-item ${value === svg ? 'selected' : ''}`}
                  style={{ background: color }}
                  onClick={() => onChange(svg)}
                >
                  {(name || 'A').charAt(0).toUpperCase()}
                </div>
              );
            })}
          </div>
        )}
        {tab === 'url' && (
          <div className="form-group" style={{ marginTop: '8px' }}>
            <input
              type="text"
              className="input"
              placeholder="https://example.com/avatar.png"
              value={urlInput}
              onChange={e => { setUrlInput(e.target.value); onChange(e.target.value); }}
            />
          </div>
        )}
        {tab === 'upload' && (
          <label className="avatar-upload" style={{ marginTop: '8px' }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            <span>点击上传图片</span>
            <input type="file" accept="image/*" onChange={handleFileUpload} />
          </label>
        )}
      </div>
    );
  };

  const handleSaveAddAgent = async () => {
    // 确定智能体类型
    const agentType = useCustomType ? addForm.customType : addForm.type;

    try {
      const newAgent = await agentApi.createAgent({
        ...addForm,
        type: agentType
      });
      setAgents([...agents, newAgent]);
      // 重新获取智能体类型列表
      const typesData = await agentApi.getAgentTypes();
      setAgentTypes(typesData.types);
      setShowAddModal(false);
      setAddForm({ name: '', type: 'general', customType: '', personality: '', config_id: null, avatar: '' });
      setUseCustomType(false);
    } catch (error) {
      console.error('Error adding agent:', error);
      // 模拟添加智能体
      const newAgent: Agent = {
        id: agents.length + 1,
        name: addForm.name,
        type: agentType,
        personality: addForm.personality,
        status: 'stopped',
        config_id: addForm.config_id ?? undefined,
        avatar: addForm.avatar || undefined,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      };
      setAgents([...agents, newAgent]);
      // 模拟更新智能体类型列表
      if (!agentTypes.includes(agentType)) {
        setAgentTypes([...agentTypes, agentType]);
      }
      setShowAddModal(false);
      setAddForm({ name: '', type: 'general', customType: '', personality: '', config_id: null, avatar: '' });
      setUseCustomType(false);
    }
  };

  const handleCancelAdd = () => {
    setShowAddModal(false);
    setAddForm({ name: '', type: 'general', customType: '', personality: '', config_id: null, avatar: '' });
    setUseCustomType(false);
  };

  // 调度面板展开/折叠
  const toggleSchedulePanel = async () => {
    const next = !showSchedulePanel;
    setShowSchedulePanel(next);
    if (next) {
      await loadAvailableScheduleAgents();
    }
  };

  // 加载可调度智能体列表
  const loadAvailableScheduleAgents = async () => {
    try {
      const data = await agentApi.getAvailableAgents();
      setAvailableScheduleAgents(data);
    } catch (error) {
      console.error('Error fetching available agents:', error);
    }
  };

  // 快速派发任务
  const handleDispatchTask = async () => {
    if (!dispatchForm.source_agent_id || !dispatchForm.target_agent_id || !dispatchForm.task_name.trim()) return;
    setScheduleLoading(true);
    setScheduleResult(null);
    try {
      const result = await agentApi.dispatchTask(Number(dispatchForm.source_agent_id), {
        source_agent_id: Number(dispatchForm.source_agent_id),
        target_agent_id: Number(dispatchForm.target_agent_id),
        task_name: dispatchForm.task_name,
        task_description: dispatchForm.task_description,
        priority: Number(dispatchForm.priority) || 1,
      });
      setScheduleResult(`任务已派发成功！任务ID: ${result.task_id || '未知'}`);
      setDispatchForm({ source_agent_id: '', target_agent_id: '', task_name: '', task_description: '', priority: '1' });
      await loadAvailableScheduleAgents();
    } catch (error) {
      console.error('Error dispatching task:', error);
      setScheduleResult('任务派发失败，请检查网络或参数');
    } finally {
      setScheduleLoading(false);
    }
  };

  // 自动调度
  const handleAutoSchedule = async () => {
    if (!autoScheduleForm.task_name.trim()) return;
    setScheduleLoading(true);
    setScheduleResult(null);
    try {
      const result = await agentApi.autoSchedule({
        task_name: autoScheduleForm.task_name,
        task_description: autoScheduleForm.task_description,
        preferred_agent_type: autoScheduleForm.preferred_agent_type || undefined,
        priority: Number(autoScheduleForm.priority) || 1,
      });
      setScheduleResult(`自动分配成功！智能体: ${result.agent_name || '未知'}，任务ID: ${result.task_id || '未知'}`);
      setAutoScheduleForm({ task_name: '', task_description: '', preferred_agent_type: '', priority: '1' });
      await loadAvailableScheduleAgents();
    } catch (error) {
      console.error('Error auto scheduling:', error);
      setScheduleResult('自动调度失败，请检查网络或参数');
    } finally {
      setScheduleLoading(false);
    }
  };

  const getStatusDot = (status: string) => {
    const isRunning = status === 'running';
    return (
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          display: 'inline-block',
          ...(isRunning
            ? {
                background: '#10b981',
                boxShadow: '0 0 8px rgba(16,185,129,0.6)',
                animation: 'pulse 2s infinite'
              }
            : {
                background: '#ef4444',
                opacity: 0.5
              })
        }}
      />
    );
  };

  const getStatusLabel = (status: string) => {
    return status === 'running' ? '运行中' : '已停止';
  };

  const personalitySectionStyle: React.CSSProperties = {
    background: 'var(--bg-surface-subtle)',
    backdropFilter: 'blur(10px)',
    WebkitBackdropFilter: 'blur(10px)',
    borderRadius: '12px',
    padding: '12px',
    border: '1px solid var(--border-color)',
    marginBottom: '12px'
  };

  return (
    <div className="agent-dashboard">
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.6; transform: scale(1.2); }
        }
        .agent-dashboard .status-badge::before {
          display: none;
        }
      `}</style>

      <div className="agent-header" style={{ justifyContent: 'flex-end' }}>
        <button className="btn btn-primary" onClick={handleAddAgent}>
          <span>添加智能体</span>
        </button>
      </div>

      <div className="agent-list">
        {agents.map((agent) => (
          <div key={agent.id} className="agent-card card">
            {editingAgent && editingAgent.id === agent.id ? (
              // 编辑模式
              <>
                <div className="form-group">
                  <label className="form-label">智能体名称</label>
                  <input
                    type="text"
                    className="input"
                    value={editForm.name}
                    onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">性格设定</label>
                  <textarea
                    className="input"
                    value={editForm.personality}
                    onChange={(e) => setEditForm({ ...editForm, personality: e.target.value })}
                    rows={4}
                    style={{ resize: 'vertical' }}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">绑定AI模型</label>
                  <select
                    className="input"
                    value={editForm.config_id ?? ''}
                    onChange={(e) => setEditForm({ ...editForm, config_id: e.target.value ? Number(e.target.value) : null })}
                  >
                    <option value="">不绑定模型</option>
                    {availableModels.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name} - {m.vendor}/{m.model_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">头像</label>
                  <AvatarPicker
                    value={editForm.avatar}
                    name={editForm.name}
                    onChange={(avatar) => setEditForm({ ...editForm, avatar })}
                  />
                </div>
                <div className="agent-actions">
                  <button
                    className="btn btn-primary"
                    onClick={handleSaveAgent}
                  >
                    <span>保存</span>
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={handleCancelEdit}
                  >
                    <span>取消</span>
                  </button>
                </div>
              </>
            ) : (
              // 查看模式
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                  <AvatarImage agent={agent} size="medium" />
                  <h3 style={{ margin: 0 }}>
                    {agent.name}
                    {agent.config_name && (
                      <span style={{
                        display: 'inline-block', padding: '2px 8px', fontSize: '11px',
                        background: 'var(--gradient-primary)', color: 'white',
                        borderRadius: 'var(--radius-badge)', marginLeft: '8px'
                      }}>
                        {agent.config_name}
                      </span>
                    )}
                  </h3>
                </div>
                <span className={`status-badge ${agent.status === 'running' ? 'success' : 'error'}`} style={{ marginBottom: '12px' }}>
                  {getStatusDot(agent.status)}
                  {getStatusLabel(agent.status)}
                </span>
                <p>类型: {agent.type}</p>
                <div style={personalitySectionStyle}>
                  <p style={{ marginBottom: '4px', fontWeight: 600 }}>性格设定:</p>
                  <p style={{ marginLeft: '10px', fontStyle: 'italic' }}>{agent.personality || '未设置'}</p>
                </div>
                <p>创建时间: {new Date(agent.created_at).toLocaleString()}</p>
                <p>更新时间: {new Date(agent.updated_at).toLocaleString()}</p>
                <div className="agent-actions">
                  {agent.status === 'stopped' ? (
                    <button
                      className="btn btn-primary"
                      onClick={() => handleStartAgent(agent.id)}
                    >
                      <span>启动</span>
                    </button>
                  ) : (
                    <button
                      className="btn btn-secondary"
                      onClick={() => handleStopAgent(agent.id)}
                    >
                      <span>停止</span>
                    </button>
                  )}
                  <button
                    className="btn btn-secondary"
                    onClick={() => handleEditAgent(agent)}
                  >
                    <span>编辑</span>
                  </button>
                </div>
              </>
            )}
          </div>
        ))}
      </div>

      {/* 智能体调度面板 */}
      <div className="card" style={{ marginTop: '24px' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            cursor: 'pointer',
            padding: '8px 0'
          }}
          onClick={toggleSchedulePanel}
        >
          <h3 style={{ margin: 0, fontSize: '1.125rem' }}>智能体调度</h3>
          <span style={{ fontSize: '1.25rem', transition: 'transform 0.2s', transform: showSchedulePanel ? 'rotate(180deg)' : 'rotate(0deg)' }}>
            ▼
          </span>
        </div>

        {showSchedulePanel && (
          <div style={{ marginTop: '16px', borderTop: '1px solid var(--border-color)', paddingTop: '16px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
              {/* 快速派发任务 */}
              <div>
                <h4 style={{ fontSize: '1rem', marginBottom: '12px' }}>快速派发任务</h4>
                <div className="form-group">
                  <label className="form-label">源智能体</label>
                  <select
                    className="input"
                    value={dispatchForm.source_agent_id}
                    onChange={(e) => setDispatchForm({ ...dispatchForm, source_agent_id: e.target.value })}
                  >
                    <option value="">选择发起者</option>
                    {agents.map((a) => (
                      <option key={a.id} value={a.id}>{a.name}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">目标智能体</label>
                  <select
                    className="input"
                    value={dispatchForm.target_agent_id}
                    onChange={(e) => setDispatchForm({ ...dispatchForm, target_agent_id: e.target.value })}
                  >
                    <option value="">选择执行者</option>
                    {agents.map((a) => (
                      <option key={a.id} value={a.id}>{a.name}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">任务名称</label>
                  <input
                    type="text"
                    className="input"
                    value={dispatchForm.task_name}
                    onChange={(e) => setDispatchForm({ ...dispatchForm, task_name: e.target.value })}
                    placeholder="请输入任务名称"
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">任务描述</label>
                  <textarea
                    className="input"
                    value={dispatchForm.task_description}
                    onChange={(e) => setDispatchForm({ ...dispatchForm, task_description: e.target.value })}
                    rows={3}
                    style={{ resize: 'vertical' }}
                    placeholder="请输入任务描述"
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">优先级 (1-5)</label>
                  <input
                    type="number"
                    className="input"
                    min={1}
                    max={5}
                    value={dispatchForm.priority}
                    onChange={(e) => setDispatchForm({ ...dispatchForm, priority: e.target.value })}
                  />
                </div>
                <button
                  className="btn btn-primary"
                  onClick={handleDispatchTask}
                  disabled={!dispatchForm.source_agent_id || !dispatchForm.target_agent_id || !dispatchForm.task_name.trim() || scheduleLoading}
                  style={{ width: '100%' }}
                >
                  <span>{scheduleLoading ? '派发中...' : '派发任务'}</span>
                </button>
              </div>

              {/* 自动调度 */}
              <div>
                <h4 style={{ fontSize: '1rem', marginBottom: '12px' }}>自动调度</h4>
                <div className="form-group">
                  <label className="form-label">任务名称</label>
                  <input
                    type="text"
                    className="input"
                    value={autoScheduleForm.task_name}
                    onChange={(e) => setAutoScheduleForm({ ...autoScheduleForm, task_name: e.target.value })}
                    placeholder="请输入任务名称"
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">任务描述</label>
                  <textarea
                    className="input"
                    value={autoScheduleForm.task_description}
                    onChange={(e) => setAutoScheduleForm({ ...autoScheduleForm, task_description: e.target.value })}
                    rows={3}
                    style={{ resize: 'vertical' }}
                    placeholder="请输入任务描述"
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">偏好智能体类型（可选）</label>
                  <input
                    type="text"
                    className="input"
                    value={autoScheduleForm.preferred_agent_type}
                    onChange={(e) => setAutoScheduleForm({ ...autoScheduleForm, preferred_agent_type: e.target.value })}
                    placeholder="例如: data_analyst"
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">优先级 (1-5)</label>
                  <input
                    type="number"
                    className="input"
                    min={1}
                    max={5}
                    value={autoScheduleForm.priority}
                    onChange={(e) => setAutoScheduleForm({ ...autoScheduleForm, priority: e.target.value })}
                  />
                </div>
                <button
                  className="btn btn-primary"
                  onClick={handleAutoSchedule}
                  disabled={!autoScheduleForm.task_name.trim() || scheduleLoading}
                  style={{ width: '100%' }}
                >
                  <span>{scheduleLoading ? '调度中...' : '自动分配'}</span>
                </button>
              </div>
            </div>

            {scheduleResult && (
              <div style={{
                marginTop: '16px',
                padding: '12px',
                borderRadius: 'var(--radius-card)',
                background: scheduleResult.includes('成功') ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
                border: `1px solid ${scheduleResult.includes('成功') ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
                color: scheduleResult.includes('成功') ? '#10b981' : '#ef4444',
                fontSize: '0.875rem'
              }}>
                {scheduleResult}
              </div>
            )}

            {/* 可调度智能体列表 */}
            <div style={{ marginTop: '24px' }}>
              <h4 style={{ fontSize: '1rem', marginBottom: '12px' }}>可调度智能体列表</h4>
              {availableScheduleAgents.length === 0 ? (
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>暂无数据</p>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>
                  {availableScheduleAgents.map((sa) => (
                    <div
                      key={sa.id}
                      style={{
                        padding: '12px',
                        borderRadius: 'var(--radius-card)',
                        background: 'var(--bg-surface-subtle)',
                        backdropFilter: 'blur(10px)',
                        WebkitBackdropFilter: 'blur(10px)',
                        border: '1px solid var(--border-color)',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <span style={{ fontWeight: 600 }}>{sa.name}</span>
                        <span style={{
                          display: 'inline-block',
                          padding: '2px 8px',
                          fontSize: '11px',
                          borderRadius: 'var(--radius-badge)',
                          background: sa.available ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)',
                          color: sa.available ? '#10b981' : '#ef4444'
                        }}>
                          {sa.available ? '可用' : '忙碌'}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                        类型: {sa.type}
                      </div>
                      {sa.config_name && (
                        <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                          模型: {sa.config_name}
                        </div>
                      )}
                      <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                        当前任务: {sa.current_tasks ?? 0}
                      </div>
                      <div style={{ width: '100%', height: '4px', background: 'var(--border-color)', borderRadius: '2px', overflow: 'hidden' }}>
                        <div style={{
                          width: `${Math.min((sa.current_tasks ?? 0) * 20, 100)}%`,
                          height: '100%',
                          background: sa.available ? 'var(--gradient-primary)' : '#ef4444',
                          borderRadius: '2px',
                          transition: 'width 0.3s ease'
                        }} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 添加智能体模态框 */}
      {showAddModal && (
        <div className="modal-overlay">
          <div className="modal">
            <h3>添加智能体</h3>
            <div className="form-group">
              <label className="form-label">智能体名称</label>
              <input
                type="text"
                className="input"
                value={addForm.name}
                onChange={(e) => setAddForm({ ...addForm, name: e.target.value })}
                placeholder="请输入智能体名称"
              />
            </div>
            <div className="form-group">
              <label className="form-label">智能体类型</label>
              {typesLoading ? (
                <div style={{ padding: '10px', textAlign: 'center', color: 'var(--text-secondary)', animation: 'pulse 2s infinite' }}>
                  加载中...
                </div>
              ) : (
                <>
                  {!useCustomType ? (
                    <select
                      className="input"
                      value={addForm.type}
                      onChange={(e) => setAddForm({ ...addForm, type: e.target.value })}
                    >
                      {agentTypes.map((type) => (
                        <option key={type} value={type}>
                          {type === 'general' ? '通用智能体' :
                           type === 'data_analyst' ? '数据分析专家' :
                           type === 'code_generator' ? '代码生成器' :
                           type}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      className="input"
                      value={addForm.customType}
                      onChange={(e) => setAddForm({ ...addForm, customType: e.target.value })}
                      placeholder="请输入自定义智能体类型"
                    />
                  )}
                  <div style={{ marginTop: '10px', display: 'flex', alignItems: 'center' }}>
                    <input
                      type="checkbox"
                      id="useCustomType"
                      checked={useCustomType}
                      onChange={(e) => setUseCustomType(e.target.checked)}
                      style={{ marginRight: '8px' }}
                    />
                    <label htmlFor="useCustomType">使用自定义类型</label>
                  </div>
                </>
              )}
            </div>
            <div className="form-group">
              <label className="form-label">性格设定</label>
              <textarea
                className="input"
                value={addForm.personality}
                onChange={(e) => setAddForm({ ...addForm, personality: e.target.value })}
                rows={4}
                style={{ resize: 'vertical' }}
                placeholder="请输入智能体的性格设定"
              />
            </div>
            <div className="form-group">
              <label className="form-label">绑定AI模型</label>
              <select
                className="input"
                value={addForm.config_id ?? ''}
                onChange={(e) => setAddForm({ ...addForm, config_id: e.target.value ? Number(e.target.value) : null })}
              >
                <option value="">不绑定模型</option>
                {availableModels.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} - {m.vendor}/{m.model_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">头像</label>
              <AvatarPicker
                value={addForm.avatar}
                name={addForm.name}
                onChange={(avatar) => setAddForm({ ...addForm, avatar })}
              />
            </div>
            <div className="modal-actions">
              <button
                className="btn btn-primary"
                onClick={handleSaveAddAgent}
                disabled={!addForm.name.trim()}
              >
                <span>保存</span>
              </button>
              <button
                className="btn btn-secondary"
                onClick={handleCancelAdd}
              >
                <span>取消</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AgentDashboard;
