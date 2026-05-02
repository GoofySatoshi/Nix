import React, { useState, useEffect, useRef, useCallback } from 'react';
import { taskApi, agentApi } from '../services/api';
import MermaidDiagram from './MermaidDiagram';

interface WorkflowStep {
  id: number;
  task_id: number;
  name: string;
  description: string;
  status: string;
  order: number;
  created_at: string;
  updated_at: string;
}

interface Task {
  id: number;
  name: string;
  description: string;
  agent_id: number;
  status: string;
  dependencies: number[];
  priority: number;
  mermaid_syntax: string;
  result?: any;
  execution_log?: string;
  created_at: string;
  updated_at: string;
  workflow_steps?: WorkflowStep[];
}

interface Agent {
  id: number;
  name: string;
  type: string;
  status: string;
}

type ViewMode = 'card' | 'table';
type FilterStatus = 'all' | 'pending' | 'running' | 'completed' | 'failed';

const TaskManager: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // 视图与筛选
  const [viewMode, setViewMode] = useState<ViewMode>('card');
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all');
  const [searchText, setSearchText] = useState('');

  // 创建模态框
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState({
    name: '', description: '', agent_id: 0,
    dependencies: [] as number[], priority: 0, mermaid_syntax: ''
  });

  // 编辑模态框
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [editForm, setEditForm] = useState({
    name: '', description: '', priority: 0,
    dependencies: [] as number[], mermaid_syntax: ''
  });

  // 详情面板
  const [detailTaskId, setDetailTaskId] = useState<number | null>(null);

  // 工作流模态框
  const [showWorkflowModal, setShowWorkflowModal] = useState(false);
  const [mermaidSyntax, setMermaidSyntax] = useState('');
  const [workflowViewMode, setWorkflowViewMode] = useState<'code' | 'preview' | 'both'>('both');

  // 删除确认
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);

  // WebSocket
  const wsRef = useRef<WebSocket | null>(null);

  // 初始化：加载任务和智能体
  useEffect(() => {
    loadTasks();
    loadAgents();
  }, []);

  // WebSocket 连接
  useEffect(() => {
    connectWebSocket();
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const connectWebSocket = () => {
    try {
      wsRef.current = new WebSocket('ws://localhost:8000/ws');
      wsRef.current.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'task_update') {
            setTasks(prev => prev.map(t =>
              t.id === msg.task_id
                ? { ...t, status: msg.status, result: msg.result || t.result, execution_log: msg.execution_log || t.execution_log }
                : t
            ));
          }
        } catch {}
      };
      wsRef.current.onclose = () => {
        setTimeout(connectWebSocket, 3000);
      };
    } catch {}
  };

  const loadTasks = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await taskApi.getTasks({
        status: filterStatus !== 'all' ? filterStatus : undefined,
        search: searchText || undefined,
      });
      setTasks(data);
    } catch (err: any) {
      setError(err.message || '加载任务失败');
    } finally {
      setLoading(false);
    }
  };

  const loadAgents = async () => {
    try {
      const data = await agentApi.getAgents();
      setAgents(data.filter((a: Agent) => a.status === 'running'));
    } catch {}
  };

  // 筛选变更时重新加载
  useEffect(() => {
    if (!loading) loadTasks();
  }, [filterStatus]);

  // 搜索（防抖）
  useEffect(() => {
    const timer = setTimeout(() => {
      if (!loading) loadTasks();
    }, 300);
    return () => clearTimeout(timer);
  }, [searchText]);

  // —— 创建任务 ——
  const handleCreateTask = () => {
    setCreateForm({ name: '', description: '', agent_id: agents[0]?.id || 0, dependencies: [], priority: 0, mermaid_syntax: '' });
    setShowCreateModal(true);
  };

  const handleSaveCreate = async () => {
    if (!createForm.name.trim()) return;
    try {
      await taskApi.createTask(createForm);
      setShowCreateModal(false);
      loadTasks();
    } catch (err: any) {
      setError(err.message);
    }
  };

  // —— 编辑任务 ——
  const handleOpenEdit = (task: Task) => {
    setEditingTask(task);
    setEditForm({
      name: task.name,
      description: task.description || '',
      priority: task.priority,
      dependencies: task.dependencies || [],
      mermaid_syntax: task.mermaid_syntax || '',
    });
    setShowEditModal(true);
  };

  const handleSaveEdit = async () => {
    if (!editingTask || !editForm.name.trim()) return;
    try {
      await taskApi.updateTask(editingTask.id, editForm);
      setShowEditModal(false);
      setEditingTask(null);
      loadTasks();
    } catch (err: any) {
      setError(err.message);
    }
  };

  // —— 删除任务 ——
  const handleDeleteTask = async () => {
    if (!deleteConfirmId) return;
    try {
      await taskApi.deleteTask(deleteConfirmId);
      setDeleteConfirmId(null);
      setDetailTaskId(null);
      loadTasks();
    } catch (err: any) {
      setError(err.message);
    }
  };

  // —— 执行任务 ——
  const handleExecuteTask = async (taskId: number) => {
    try {
      await taskApi.executeTask(taskId);
      loadTasks();
    } catch (err: any) {
      setError(err.message);
    }
  };

  // —— 工作流管理 ——
  const handleOpenWorkflow = (task: Task) => {
    setMermaidSyntax(task.mermaid_syntax || '');
    setShowWorkflowModal(true);
  };

  const handleCloseWorkflow = async () => {
    if (detailTaskId) {
      try {
        await taskApi.updateTask(detailTaskId, { mermaid_syntax: mermaidSyntax });
        loadTasks();
      } catch {}
    }
    setShowWorkflowModal(false);
  };

  // —— 依赖勾选辅助 ——
  const handleDependencyToggle = (taskId: number, checked: boolean, form: 'create' | 'edit') => {
    if (form === 'create') {
      const deps = checked
        ? [...createForm.dependencies, taskId]
        : createForm.dependencies.filter(id => id !== taskId);
      setCreateForm(prev => ({ ...prev, dependencies: deps }));
    } else {
      const deps = checked
        ? [...editForm.dependencies, taskId]
        : editForm.dependencies.filter(id => id !== taskId);
      setEditForm((prev: typeof editForm) => ({ ...prev, dependencies: deps }));
    }
  };

  // —— 过滤后的任务列表 ——
  const filteredTasks = tasks;

  // —— 渲染辅助 ——
  const statusLabels: Record<string, string> = {
    pending: '待处理', running: '运行中', completed: '已完成', failed: '失败'
  };
  const statusBadgeClass = (s: string) => `status-badge ${s === 'completed' ? 'success' : s === 'failed' ? 'error' : s === 'running' ? 'info' : 'warning'}`;

  // ===== 加载状态 =====
  if (loading && tasks.length === 0) {
    return (
      <div className="card glass">
        <div style={{ display: 'flex', justifyContent: 'center', padding: '40px', color: 'var(--text-primary)' }}>
          加载中...
        </div>
      </div>
    );
  }

  // ===== 主界面 =====
  return (
    <div className="task-manager">
      {/* 错误提示 */}
      {error && (
        <div className="auth-error" style={{ marginBottom: '16px' }}>
          {error}
          <button onClick={() => setError('')} style={{ marginLeft: '12px', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontWeight: 700 }}>x</button>
        </div>
      )}

      {/* ====== 顶部工具栏 ====== */}
      <div className="task-toolbar">
        <div className="task-toolbar-left">
          <button className="btn btn-primary" onClick={handleCreateTask}>+ 创建任务</button>
          <button className="btn btn-secondary" onClick={loadTasks}>刷新</button>
        </div>
        <div className="task-toolbar-center">
          <div className="filter-tabs">
            {(['all', 'pending', 'running', 'completed', 'failed'] as FilterStatus[]).map(s => (
              <button
                key={s}
                className={`filter-tab ${filterStatus === s ? 'active' : ''}`}
                onClick={() => setFilterStatus(s)}
              >
                {s === 'all' ? '全部' : statusLabels[s]}
              </button>
            ))}
          </div>
        </div>
        <div className="task-toolbar-right">
          <input
            type="text"
            className="input"
            placeholder="搜索任务..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: '200px' }}
          />
          <div className="view-toggle">
            <button className={`btn btn-sm ${viewMode === 'card' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setViewMode('card')}>卡片</button>
            <button className={`btn btn-sm ${viewMode === 'table' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setViewMode('table')}>表格</button>
          </div>
        </div>
      </div>

      {/* ====== 任务列表 ====== */}
      {filteredTasks.length === 0 ? (
        <div className="card glass" style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
          <p style={{ fontSize: '1.2rem', marginBottom: '8px' }}>暂无任务</p>
          <p>点击「创建任务」开始</p>
        </div>
      ) : viewMode === 'card' ? (
        <div className="task-list">
          {filteredTasks.map(task => (
            <div key={task.id} className="task-card card">
              <h3>{task.name}</h3>
              <div className={statusBadgeClass(task.status)}>{statusLabels[task.status]}</div>
              <p>描述: {task.description || '无'}</p>
              <p>智能体ID: {task.agent_id || '未分配'}</p>
              <div style={{ marginBottom: '8px' }}>
                <p style={{ marginBottom: '4px' }}>优先级: {task.priority}</p>
                <div style={{ height: '4px', width: `${Math.min(task.priority * 10, 100)}%`, background: 'linear-gradient(90deg, var(--color-primary-1), var(--color-primary-2), var(--color-primary-3))', borderRadius: '2px' }} />
              </div>
              <p>依赖: {task.dependencies?.length ? task.dependencies.join(', ') : '无'}</p>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{new Date(task.created_at).toLocaleString()}</p>
              <div className="agent-actions">
                <button className="btn btn-secondary" onClick={() => setDetailTaskId(detailTaskId === task.id ? null : task.id)}>查看详情</button>
                <button className="btn btn-secondary" onClick={() => handleOpenEdit(task)}>编辑</button>
                {task.status === 'pending' && (
                  <button className="btn btn-primary" onClick={() => handleExecuteTask(task.id)}>执行</button>
                )}
                <button className="btn btn-secondary" onClick={() => handleOpenWorkflow(task)}>工作流</button>
                <button className="btn btn-danger" onClick={() => setDeleteConfirmId(task.id)}>删除</button>
              </div>

              {/* 内联详情面板 */}
              {detailTaskId === task.id && (
                <div className="task-detail-panel">
                  <h4>执行详情</h4>
                  {task.execution_log ? (
                    <div className="execution-log">
                      <pre>{task.execution_log}</pre>
                    </div>
                  ) : (
                    <p style={{ color: 'var(--text-muted)' }}>暂无执行日志</p>
                  )}
                  {task.result && (
                    <div className="execution-log" style={{ marginTop: '12px' }}>
                      <strong>执行结果:</strong>
                      <pre>{JSON.stringify(task.result, null, 2)}</pre>
                    </div>
                  )}
                  {task.workflow_steps && task.workflow_steps.length > 0 && (
                    <div style={{ marginTop: '12px' }}>
                      <strong>工作流步骤:</strong>
                      <div className="step-progress">
                        {task.workflow_steps.map(step => (
                          <div key={step.id} className={`step-item ${step.status}`}>
                            <div className="step-dot" />
                            <div>
                              <span style={{ fontWeight: 600 }}>{step.name}</span>
                              <span style={{ marginLeft: '8px', fontSize: '0.8rem' }} className={`status-badge ${step.status === 'completed' ? 'success' : step.status === 'failed' ? 'error' : 'warning'}`}>
                                {statusLabels[step.status] || step.status}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        /* ====== 表格视图 ====== */
        <div className="card" style={{ overflow: 'auto' }}>
          <table className="task-table">
            <thead>
              <tr>
                <th>ID</th><th>名称</th><th>描述</th><th>智能体</th><th>状态</th><th>优先级</th><th>依赖</th><th>创建时间</th><th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredTasks.map(task => (
                <tr key={task.id}>
                  <td>{task.id}</td>
                  <td>{task.name}</td>
                  <td style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{task.description || '-'}</td>
                  <td>{task.agent_id || '-'}</td>
                  <td><span className={statusBadgeClass(task.status)}>{statusLabels[task.status]}</span></td>
                  <td>{task.priority}</td>
                  <td>{task.dependencies?.length ? task.dependencies.join(',') : '-'}</td>
                  <td style={{ fontSize: '0.8rem' }}>{new Date(task.created_at).toLocaleDateString()}</td>
                  <td>
                    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                      <button className="btn btn-sm btn-secondary" onClick={() => setDetailTaskId(detailTaskId === task.id ? null : task.id)}>详情</button>
                      <button className="btn btn-sm btn-secondary" onClick={() => handleOpenEdit(task)}>编辑</button>
                      {task.status === 'pending' && (
                        <button className="btn btn-sm btn-primary" onClick={() => handleExecuteTask(task.id)}>执行</button>
                      )}
                      <button className="btn btn-sm btn-secondary" onClick={() => handleOpenWorkflow(task)}>流程</button>
                      <button className="btn btn-sm btn-danger" onClick={() => setDeleteConfirmId(task.id)}>删除</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}



      {/* ====== 创建任务模态框 ====== */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '560px' }}>
            <h3>创建任务</h3>
            <div className="form-group">
              <label className="form-label">任务名称</label>
              <input type="text" className="input" value={createForm.name} onChange={e => setCreateForm(p => ({ ...p, name: e.target.value }))} placeholder="请输入任务名称" />
            </div>
            <div className="form-group">
              <label className="form-label">任务描述</label>
              <textarea className="input" value={createForm.description} onChange={e => setCreateForm(p => ({ ...p, description: e.target.value }))} rows={3} style={{ resize: 'vertical' }} placeholder="请输入任务描述" />
            </div>
            <div className="form-group">
              <label className="form-label">智能体</label>
              <select className="input" value={createForm.agent_id} onChange={e => setCreateForm(p => ({ ...p, agent_id: parseInt(e.target.value) }))}>
                <option value={0}>-- 选择智能体 --</option>
                {agents.map(a => (
                  <option key={a.id} value={a.id}>{a.name} ({a.type})</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">优先级 (0-10)</label>
              <input type="number" className="input" value={createForm.priority} onChange={e => setCreateForm(p => ({ ...p, priority: parseInt(e.target.value) || 0 }))} min={0} max={10} />
            </div>
            <div className="form-group">
              <label className="form-label">依赖任务</label>
              <div style={{ maxHeight: '120px', overflowY: 'auto', background: 'var(--bg-surface-subtle)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '12px' }}>
                {tasks.filter(t => t.id !== (editingTask?.id || -1)).map(t => (
                  <div key={t.id} style={{ display: 'flex', alignItems: 'center', marginBottom: '4px' }}>
                    <input type="checkbox" id={`cdep-${t.id}`} checked={createForm.dependencies.includes(t.id)} onChange={e => handleDependencyToggle(t.id, e.target.checked, 'create')} style={{ marginRight: '8px' }} />
                    <label htmlFor={`cdep-${t.id}`} style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{t.name} (ID:{t.id})</label>
                  </div>
                ))}
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Mermaid 工作流</label>
              <textarea className="input" value={createForm.mermaid_syntax} onChange={e => setCreateForm(p => ({ ...p, mermaid_syntax: e.target.value }))} rows={4} style={{ resize: 'vertical', fontFamily: 'monospace' }} placeholder="graph TD\n  A[开始] --> B[步骤1]\n  B --> C[结束]" />
            </div>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={handleSaveCreate} disabled={!createForm.name.trim()}>保存</button>
              <button className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>取消</button>
            </div>
          </div>
        </div>
      )}

      {/* ====== 编辑任务模态框 ====== */}
      {showEditModal && editingTask && (
        <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '560px' }}>
            <h3>编辑任务</h3>
            <div className="form-group">
              <label className="form-label">任务名称</label>
              <input type="text" className="input" value={editForm.name} onChange={e => setEditForm(p => ({ ...p, name: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">任务描述</label>
              <textarea className="input" value={editForm.description} onChange={e => setEditForm(p => ({ ...p, description: e.target.value }))} rows={3} style={{ resize: 'vertical' }} />
            </div>
            <div className="form-group">
              <label className="form-label">优先级 (0-10)</label>
              <input type="number" className="input" value={editForm.priority} onChange={e => setEditForm(p => ({ ...p, priority: parseInt(e.target.value) || 0 }))} min={0} max={10} />
            </div>
            <div className="form-group">
              <label className="form-label">依赖任务</label>
              <div style={{ maxHeight: '120px', overflowY: 'auto', background: 'var(--bg-surface-subtle)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '12px' }}>
                {tasks.filter(t => t.id !== editingTask.id).map(t => (
                  <div key={t.id} style={{ display: 'flex', alignItems: 'center', marginBottom: '4px' }}>
                    <input type="checkbox" id={`edep-${t.id}`} checked={editForm.dependencies.includes(t.id)} onChange={e => handleDependencyToggle(t.id, e.target.checked, 'edit')} style={{ marginRight: '8px' }} />
                    <label htmlFor={`edep-${t.id}`} style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{t.name} (ID:{t.id})</label>
                  </div>
                ))}
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Mermaid 工作流</label>
              <textarea className="input" value={editForm.mermaid_syntax} onChange={e => setEditForm(p => ({ ...p, mermaid_syntax: e.target.value }))} rows={4} style={{ resize: 'vertical', fontFamily: 'monospace' }} />
            </div>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={handleSaveEdit} disabled={!editForm.name.trim()}>保存</button>
              <button className="btn btn-secondary" onClick={() => { setShowEditModal(false); setEditingTask(null); }}>取消</button>
            </div>
          </div>
        </div>
      )}

      {/* ====== 删除确认 ====== */}
      {deleteConfirmId && (
        <div className="modal-overlay" onClick={() => setDeleteConfirmId(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '400px', textAlign: 'center' }}>
            <h3>确认删除</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '20px' }}>确定要删除任务 #{deleteConfirmId} 吗？此操作不可撤销。</p>
            <div className="modal-actions" style={{ justifyContent: 'center' }}>
              <button className="btn btn-danger" onClick={handleDeleteTask}>确认删除</button>
              <button className="btn btn-secondary" onClick={() => setDeleteConfirmId(null)}>取消</button>
            </div>
          </div>
        </div>
      )}

      {/* ====== 工作流管理模态框 ====== */}
      {showWorkflowModal && (
        <div className="modal-overlay" onClick={handleCloseWorkflow}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ width: '95%', maxWidth: '1400px', maxHeight: '95vh' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3>工作流管理</h3>
              <div style={{ display: 'flex', gap: '8px' }}>
                {(['code', 'preview', 'both'] as const).map(m => (
                  <button key={m} className={`btn btn-sm ${workflowViewMode === m ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setWorkflowViewMode(m)}>
                    {m === 'code' ? '代码' : m === 'preview' ? '预览' : '代码+预览'}
                  </button>
                ))}
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: workflowViewMode === 'both' ? 'row' : 'column', gap: '16px', marginBottom: '16px', height: 'calc(95vh - 120px)' }}>
              {(workflowViewMode === 'code' || workflowViewMode === 'both') && (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--bg-surface-subtle)', border: '1px solid var(--border-color)', borderRadius: '12px', overflow: 'hidden' }}>
                  <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-color)', background: 'var(--glass-bg)' }}>
                    <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>Mermaid 语法</h4>
                  </div>
                  <div style={{ flex: 1, padding: '16px', overflow: 'auto' }}>
                    <textarea className="input" value={mermaidSyntax} onChange={e => setMermaidSyntax(e.target.value)}
                      style={{ width: '100%', height: '100%', resize: 'none', fontFamily: 'Monaco, monospace', lineHeight: 1.6 }} />
                  </div>
                </div>
              )}
              {(workflowViewMode === 'preview' || workflowViewMode === 'both') && (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--bg-surface-subtle)', border: '1px solid var(--border-color)', borderRadius: '12px', overflow: 'hidden' }}>
                  <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-color)', background: 'var(--glass-bg)' }}>
                    <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>流程图预览</h4>
                  </div>
                  <div style={{ flex: 1, padding: '16px', overflow: 'auto' }}>
                    {mermaidSyntax ? <MermaidDiagram code={mermaidSyntax} /> : (
                      <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px' }}>请在左侧编辑器中添加 Mermaid 语法</div>
                    )}
                  </div>
                </div>
              )}
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={handleCloseWorkflow}>关闭</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TaskManager;
