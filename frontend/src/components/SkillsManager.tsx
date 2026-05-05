import React, { useState, useEffect, useCallback } from 'react';
import { skillsApi, memoryApi, agentApi } from '../services/api';

interface TreeNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  children?: TreeNode[];
}

const SkillsManager: React.FC = () => {
  const [tree, setTree] = useState<TreeNode[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string>('');
  const [editContent, setEditContent] = useState<string>('');
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [showNewFileModal, setShowNewFileModal] = useState(false);
  const [showNewDirModal, setShowNewDirModal] = useState(false);
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<{ path: string; type: 'file' | 'directory' } | null>(null);

  // 记忆管理 State
  const [activeTab, setActiveTab] = useState<'skills' | 'memories'>('skills');
  const [memorySubTab, setMemorySubTab] = useState<'project' | 'agent'>('project');
  const [agents, setAgents] = useState<any[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>('');
  const [memories, setMemories] = useState<Array<{ category: string; content: string }>>([]);
  const [memoryLastUpdated, setMemoryLastUpdated] = useState<string | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [projectMemories, setProjectMemories] = useState<Array<{ category: string; content: string }>>([]);
  const [projectCategories, setProjectCategories] = useState<string[]>([]);
  const [projectMemoryLastUpdated, setProjectMemoryLastUpdated] = useState<string | null>(null);
  const [projectRawContent, setProjectRawContent] = useState<string>('');
  const [showAddMemory, setShowAddMemory] = useState(false);
  const [newMemoryCategory, setNewMemoryCategory] = useState('');
  const [newMemoryContent, setNewMemoryContent] = useState('');
  const [isRefining, setIsRefining] = useState(false);
  const [memoryMessage, setMemoryMessage] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [showRawContent, setShowRawContent] = useState(false);
  const [rawContent, setRawContent] = useState<string>('');
  const [editingMemory, setEditingMemory] = useState<{category: string; content: string} | null>(null);
  const [editMemoryContent, setEditMemoryContent] = useState('');

  // 新建文件表单
  const [newFilePath, setNewFilePath] = useState('');
  const [newFileContent, setNewFileContent] = useState('');
  const [newDirPath, setNewDirPath] = useState('');

  const showMsg = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 3000);
  };

  const loadTree = useCallback(async () => {
    setLoading(true);
    try {
      const data = await skillsApi.getTree();
      setTree(data.tree || []);
    } catch (err: any) {
      showMsg('error', err.message || '加载目录树失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTree();
  }, [loadTree]);

  const loadFile = async (path: string) => {
    try {
      const data = await skillsApi.getFile(path);
      setFileContent(data.content);
      setEditContent(data.content);
      setSelectedFile(path);
      setIsEditing(false);
    } catch (err: any) {
      showMsg('error', err.message || '加载文件失败');
    }
  };

  const handleSave = async () => {
    if (!selectedFile) return;
    try {
      await skillsApi.updateFile({ path: selectedFile, content: editContent });
      setFileContent(editContent);
      setIsEditing(false);
      showMsg('success', '文件已保存');
    } catch (err: any) {
      showMsg('error', err.message || '保存失败');
    }
  };

  const handleCreateFile = async () => {
    if (!newFilePath.trim()) return;
    try {
      await skillsApi.createFile({ path: newFilePath.trim(), content: newFileContent });
      setShowNewFileModal(false);
      setNewFilePath('');
      setNewFileContent('');
      showMsg('success', '文件已创建');
      loadTree();
    } catch (err: any) {
      showMsg('error', err.message || '创建文件失败');
    }
  };

  const handleCreateDirectory = async () => {
    if (!newDirPath.trim()) return;
    try {
      await skillsApi.createDirectory(newDirPath.trim());
      setShowNewDirModal(false);
      setNewDirPath('');
      showMsg('success', '目录已创建');
      loadTree();
    } catch (err: any) {
      showMsg('error', err.message || '创建目录失败');
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    try {
      if (deleteConfirm.type === 'file') {
        await skillsApi.deleteFile(deleteConfirm.path);
        if (selectedFile === deleteConfirm.path) {
          setSelectedFile(null);
          setFileContent('');
          setEditContent('');
          setIsEditing(false);
        }
      } else {
        await skillsApi.deleteDirectory(deleteConfirm.path);
      }
      setDeleteConfirm(null);
      showMsg('success', '删除成功');
      loadTree();
    } catch (err: any) {
      showMsg('error', err.message || '删除失败');
    }
  };

  const toggleDir = (path: string) => {
    setExpandedDirs(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  // 默认展开所有目录
  useEffect(() => {
    const expandAll = (nodes: TreeNode[]) => {
      nodes.forEach(node => {
        if (node.type === 'directory') {
          setExpandedDirs(prev => new Set(prev).add(node.path));
          if (node.children) expandAll(node.children);
        }
      });
    };
    if (tree.length > 0) {
      expandAll(tree);
    }
  }, [tree]);

  // 记忆管理加载与操作
  useEffect(() => {
    if (activeTab === 'memories') {
      loadCategories();
      if (memorySubTab === 'agent') {
        loadAgents();
      } else {
        loadProjectMemories();
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, memorySubTab]);

  useEffect(() => {
    if (selectedAgent && memorySubTab === 'agent') {
      loadMemories(selectedAgent);
    }
  }, [selectedAgent, memorySubTab]);

  const loadAgents = async () => {
    try {
      const data = await agentApi.getAgents();
      setAgents(data);
      if (data.length > 0 && !selectedAgent) {
        setSelectedAgent(data[0].name);
      }
    } catch (e) { console.error(e); }
  };

  const loadCategories = async () => {
    try {
      const data = await memoryApi.getCategories();
      setCategories(data.categories);
      setProjectCategories(data.project_categories);
      if (memorySubTab === 'project' && data.project_categories.length > 0) {
        setNewMemoryCategory(data.project_categories[0]);
      } else if (memorySubTab === 'agent' && data.categories.length > 0) {
        setNewMemoryCategory(data.categories[0]);
      }
    } catch (e) { console.error(e); }
  };

  const loadMemories = async (agentName: string) => {
    try {
      const data = await memoryApi.getMemories(agentName);
      setMemories(data.memories);
      setMemoryLastUpdated(data.last_updated);
      setRawContent(data.raw_content || '');
    } catch (e) { console.error(e); }
  };

  const loadProjectMemories = async () => {
    try {
      const data = await memoryApi.getProjectMemories();
      setProjectMemories(data.memories);
      setProjectMemoryLastUpdated(data.last_updated);
      setProjectRawContent(data.raw_content || '');
    } catch (e) { console.error(e); }
  };

  const handleAddMemory = async () => {
    const isProject = memorySubTab === 'project';
    const targetAgent = isProject ? 'project' : selectedAgent;
    if (!targetAgent || !newMemoryContent.trim()) return;
    try {
      const res = await memoryApi.addMemory(targetAgent, {
        category: newMemoryCategory,
        content: newMemoryContent.trim(),
        ...(isProject ? { workspace: '' } : {}),
      });
      if (res.success) {
        setShowAddMemory(false);
        setNewMemoryContent('');
        if (isProject) {
          loadProjectMemories();
        } else {
          loadMemories(selectedAgent);
        }
        setMemoryMessage('记忆添加成功');
      } else {
        setMemoryMessage(res.message);
      }
    } catch (e: any) { setMemoryMessage('添加失败: ' + e.message); }
    setTimeout(() => setMemoryMessage(''), 3000);
  };

  const handleDeleteMemory = async (category: string, content: string) => {
    const isProject = memorySubTab === 'project';
    const targetAgent = isProject ? 'project' : selectedAgent;
    if (!targetAgent) return;
    try {
      await memoryApi.deleteMemory(targetAgent, {
        category,
        content,
        ...(isProject ? { workspace: '' } : {}),
      });
      if (isProject) {
        loadProjectMemories();
      } else {
        loadMemories(selectedAgent);
      }
      setMemoryMessage('记忆已删除');
    } catch (e: any) { setMemoryMessage('删除失败'); }
    setTimeout(() => setMemoryMessage(''), 3000);
  };

  const handleRefineMemories = async () => {
    if (!selectedAgent) return;
    setIsRefining(true);
    setMemoryMessage('正在使用 AI 整理记忆...');
    try {
      const res = await memoryApi.refineMemories(selectedAgent);
      if (res.success) {
        setMemories(res.refined_memories);
        setRawContent(res.raw_content || '');
        setMemoryMessage(res.message);
      } else {
        setMemoryMessage(res.message);
      }
    } catch (e: any) {
      setMemoryMessage('整理失败: ' + (e.message || '请检查 API Key 配置'));
    }
    setIsRefining(false);
    setTimeout(() => setMemoryMessage(''), 5000);
  };

  const handleUpdateMemory = async () => {
    const isProject = memorySubTab === 'project';
    const targetAgent = isProject ? 'project' : selectedAgent;
    if (!targetAgent || !editingMemory || !editMemoryContent.trim()) return;
    try {
      const res = await memoryApi.updateMemory(targetAgent, {
        category: editingMemory.category,
        old_content: editingMemory.content,
        new_content: editMemoryContent.trim(),
        ...(isProject ? { workspace: '' } : {}),
      });
      if (res.success) {
        setEditingMemory(null);
        setEditMemoryContent('');
        if (isProject) {
          loadProjectMemories();
        } else {
          loadMemories(selectedAgent);
        }
        setMemoryMessage('记忆更新成功');
      } else {
        setMemoryMessage(res.message);
      }
    } catch (e: any) { setMemoryMessage('更新失败: ' + e.message); }
    setTimeout(() => setMemoryMessage(''), 3000);
  };

  const renderTree = (nodes: TreeNode[]) => {
    return nodes.map(node => (
      <div key={node.path} className="tree-node">
        <div
          className={`tree-node-item ${selectedFile === node.path && node.type === 'file' ? 'selected' : ''}`}
          onClick={() => {
            if (node.type === 'directory') {
              toggleDir(node.path);
            } else {
              loadFile(node.path);
            }
          }}
        >
          <span className="tree-node-icon">
            {node.type === 'directory' ? (expandedDirs.has(node.path) ? '📂' : '📁') : '📄'}
          </span>
          <span className="tree-node-name">{node.name}</span>
          <span className="tree-node-actions">
            <button
              className="btn btn-sm btn-danger"
              onClick={e => {
                e.stopPropagation();
                setDeleteConfirm({ path: node.path, type: node.type });
              }}
              title="删除"
            >
              删除
            </button>
          </span>
        </div>
        {node.type === 'directory' && expandedDirs.has(node.path) && node.children && (
          <div className="tree-node-children">
            {renderTree(node.children)}
          </div>
        )}
      </div>
    ));
  };

  const renderMarkdown = (content: string) => {
    const lines = content.split('\n');
    const elements: React.ReactNode[] = [];
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      if (line.startsWith('```')) {
        const lang = line.slice(3).trim();
        const codeLines: string[] = [];
        i++;
        while (i < lines.length && !lines[i].startsWith('```')) {
          codeLines.push(lines[i]);
          i++;
        }
        i++; // skip closing ```
        elements.push(
          <pre
            key={elements.length}
            style={{
              background: 'rgba(0,0,0,0.25)',
              border: '1px solid var(--glass-border)',
              borderRadius: 'var(--radius-input)',
              padding: '12px 16px',
              margin: '8px 0',
              overflowX: 'auto',
              fontFamily: "'SF Mono', 'Fira Code', monospace",
              fontSize: '13px',
              lineHeight: 1.5,
              color: 'var(--text-secondary)',
            }}
          >
            {lang && (
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase' }}>
                {lang}
              </div>
            )}
            <code>{codeLines.join('\n')}</code>
          </pre>
        );
        continue;
      }
      if (line.startsWith('### ')) {
        elements.push(<h3 key={elements.length}>{line.slice(4)}</h3>);
      } else if (line.startsWith('## ')) {
        elements.push(<h2 key={elements.length}>{line.slice(3)}</h2>);
      } else if (line.startsWith('# ')) {
        elements.push(<h1 key={elements.length}>{line.slice(2)}</h1>);
      } else if (line.startsWith('- ')) {
        elements.push(<li key={elements.length}>{line.slice(2)}</li>);
      } else if (line.trim() === '') {
        elements.push(<br key={elements.length} />);
      } else {
        elements.push(<p key={elements.length} style={{ margin: '4px 0' }}>{line}</p>);
      }
      i++;
    }
    return elements;
  };

  return (
    <div className="skills-manager">
      {/* 顶部标题和按钮 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h3>Skills 管理</h3>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', margin: '4px 0 0' }}>
            管理 Markdown 技能文件，支持目录浏览和文件编辑
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-primary" onClick={() => setShowNewFileModal(true)}>
            + 新建文件
          </button>
          <button className="btn btn-secondary" onClick={() => setShowNewDirModal(true)}>
            + 新建目录
          </button>
        </div>
      </div>

      {/* Tab 切换 */}
      <div className="skills-tabs">
        <button
          className={`skills-tab ${activeTab === 'skills' ? 'active' : ''}`}
          onClick={() => setActiveTab('skills')}
        >
          📄 Skill 文件管理
        </button>
        <button
          className={`skills-tab ${activeTab === 'memories' ? 'active' : ''}`}
          onClick={() => setActiveTab('memories')}
        >
          🧠 智能体记忆管理
        </button>
      </div>

      {activeTab === 'skills' && (
        <>
      {/* 消息提示 */}
      {message && (
        <div className={`settings-message ${message.type}`} style={{ marginBottom: '16px' }}>
          <span>{message.text}</span>
          <button onClick={() => setMessage(null)} className="settings-message-close">x</button>
        </div>
      )}

      {/* 主内容区 */}
      <div className="skills-container">
        {/* 左侧目录树 */}
        <div className="skills-sidebar">
          {loading && tree.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>加载中...</div>
          ) : tree.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
              <p>暂无技能文件</p>
            </div>
          ) : (
            renderTree(tree)
          )}
        </div>

        {/* 右侧内容区 */}
        <div className="skills-content">
          {!selectedFile ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', gap: '12px' }}>
              <span style={{ fontSize: '3rem', opacity: 0.5 }}>📄</span>
              <p>在左侧目录树中选择一个文件以查看内容</p>
            </div>
          ) : (
            <>
              <div className="skills-content-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0 }}>
                  <span style={{ fontSize: '1.1rem' }}>📄</span>
                  <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {selectedFile}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {isEditing ? (
                    <>
                      <button className="btn btn-sm btn-primary" onClick={handleSave}>保存</button>
                      <button className="btn btn-sm btn-secondary" onClick={() => { setIsEditing(false); setEditContent(fileContent); }}>取消</button>
                    </>
                  ) : (
                    <button className="btn btn-sm btn-secondary" onClick={() => setIsEditing(true)}>编辑</button>
                  )}
                  <button className="btn btn-sm btn-danger" onClick={() => setDeleteConfirm({ path: selectedFile, type: 'file' })}>删除</button>
                </div>
              </div>
              <div className="skills-content-body">
                {isEditing ? (
                  <textarea
                    className="skills-editor"
                    value={editContent}
                    onChange={e => setEditContent(e.target.value)}
                    spellCheck={false}
                  />
                ) : (
                  <div className="markdown-view">{renderMarkdown(fileContent)}</div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* ===== 新建文件模态框 ===== */}
      {showNewFileModal && (
        <div className="modal-overlay" onClick={() => setShowNewFileModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>新建文件</h3>
            <div className="form-group">
              <label className="form-label">文件路径</label>
              <input
                type="text"
                className="input"
                value={newFilePath}
                onChange={e => setNewFilePath(e.target.value)}
                placeholder="例如：coding/python-guide.md"
                autoFocus
              />
            </div>
            <div className="form-group">
              <label className="form-label">初始内容（可选）</label>
              <textarea
                className="skills-editor"
                style={{ minHeight: '180px', resize: 'vertical' }}
                value={newFileContent}
                onChange={e => setNewFileContent(e.target.value)}
                placeholder="# 标题\n\n内容..."
              />
            </div>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={handleCreateFile} disabled={!newFilePath.trim()}>
                创建
              </button>
              <button className="btn btn-secondary" onClick={() => { setShowNewFileModal(false); setNewFilePath(''); setNewFileContent(''); }}>
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===== 新建目录模态框 ===== */}
      {showNewDirModal && (
        <div className="modal-overlay" onClick={() => setShowNewDirModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>新建目录</h3>
            <div className="form-group">
              <label className="form-label">目录路径</label>
              <input
                type="text"
                className="input"
                value={newDirPath}
                onChange={e => setNewDirPath(e.target.value)}
                placeholder="例如：database/mysql"
                autoFocus
              />
            </div>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={handleCreateDirectory} disabled={!newDirPath.trim()}>
                创建
              </button>
              <button className="btn btn-secondary" onClick={() => { setShowNewDirModal(false); setNewDirPath(''); }}>
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===== 删除确认 ===== */}
      {deleteConfirm && (
        <div className="modal-overlay" onClick={() => setDeleteConfirm(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '400px', textAlign: 'center' }}>
            <h3>确认删除</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '8px' }}>
              确定要删除这个{deleteConfirm.type === 'file' ? '文件' : '目录'}吗？
            </p>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '20px', wordBreak: 'break-all' }}>
              {deleteConfirm.path}
            </p>
            <div className="modal-actions" style={{ justifyContent: 'center' }}>
              <button className="btn btn-danger" onClick={handleDelete}>确认删除</button>
              <button className="btn btn-secondary" onClick={() => setDeleteConfirm(null)}>取消</button>
            </div>
          </div>
        </div>
      )}
        </>
      )}

      {activeTab === 'memories' && (
        <div className="memory-manager">
          {/* 消息提示 */}
          {memoryMessage && (
            <div className={`memory-toast ${memoryMessage.includes('失败') || memoryMessage.includes('错误') ? 'error' : 'success'}`}>
              {memoryMessage}
            </div>
          )}

          {/* 子视图切换 */}
          <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
            <button
              onClick={() => { setMemorySubTab('project'); setSelectedCategory('all'); }}
              style={{
                padding: '6px 16px',
                borderRadius: '20px',
                border: 'none',
                background: memorySubTab === 'project' ? 'rgba(99, 102, 241, 0.3)' : 'rgba(255,255,255,0.05)',
                color: memorySubTab === 'project' ? '#fff' : 'var(--text-secondary)',
                cursor: 'pointer',
                fontSize: '14px',
                transition: 'all 0.2s',
              }}
            >
              📋 项目记忆
            </button>
            <button
              onClick={() => { setMemorySubTab('agent'); setSelectedCategory('all'); }}
              style={{
                padding: '6px 16px',
                borderRadius: '20px',
                border: 'none',
                background: memorySubTab === 'agent' ? 'rgba(99, 102, 241, 0.3)' : 'rgba(255,255,255,0.05)',
                color: memorySubTab === 'agent' ? '#fff' : 'var(--text-secondary)',
                cursor: 'pointer',
                fontSize: '14px',
                transition: 'all 0.2s',
              }}
            >
              🤖 智能体记忆
            </button>
          </div>

          {/* 顶部区域 */}
          <div className="memory-header">
            <h3 className="memory-title">
              {memorySubTab === 'project' ? '📋 项目记忆' : '🧠 智能体记忆'}
            </h3>
            {memorySubTab === 'project' ? (
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span>📂</span>
                <span>存储位置：.nix/project-memory.md</span>
              </div>
            ) : (
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span>📂</span>
                <span>存储位置：skills/{selectedAgent}-SOUL.md</span>
              </div>
            )}
            <div className="memory-header-row">
              {memorySubTab === 'agent' && (
                <div className="memory-agent-select-wrapper">
                  <select
                    className="memory-agent-select-input"
                    value={selectedAgent}
                    onChange={e => setSelectedAgent(e.target.value)}
                  >
                    {agents.map(a => (
                      <option key={a.id} value={a.name}>{a.name}</option>
                    ))}
                  </select>
                </div>
              )}
              <div className="memory-stats-bar">
                <span className="memory-stat-item">
                  <span className="memory-stat-icon">📊</span>
                  {(memorySubTab === 'project' ? projectMemories : memories).length}条记忆
                </span>
                {(memorySubTab === 'project' ? projectMemoryLastUpdated : memoryLastUpdated) && (
                  <span className="memory-stat-item">
                    <span className="memory-stat-icon">⏰</span>
                    最后更新: {(() => {
                      const ts = memorySubTab === 'project' ? projectMemoryLastUpdated : memoryLastUpdated;
                      const date = new Date(ts!);
                      const now = new Date();
                      const diffMs = now.getTime() - date.getTime();
                      const diffMins = Math.floor(diffMs / 60000);
                      const diffHours = Math.floor(diffMins / 60);
                      const diffDays = Math.floor(diffHours / 24);
                      if (diffMins < 1) return '刚刚';
                      if (diffMins < 60) return `${diffMins}分钟前`;
                      if (diffHours < 24) return `${diffHours}小时前`;
                      if (diffDays < 30) return `${diffDays}天前`;
                      return date.toLocaleDateString();
                    })()}
                  </span>
                )}
              </div>
            </div>
            <div className="memory-header-actions">
              <button className="memory-btn memory-btn-add" onClick={() => setShowAddMemory(true)}>
                <span>+</span> 添加
              </button>
              {memorySubTab === 'agent' && (
                <button
                  className={`memory-btn memory-btn-refine ${isRefining ? 'refining' : ''}`}
                  onClick={handleRefineMemories}
                  disabled={isRefining || memories.length === 0}
                >
                  <span className={`refine-icon ${isRefining ? 'spinning' : ''}`}>✨</span>
                  {isRefining ? '正在使用 AI 提炼记忆...' : 'AI整理记忆'}
                </button>
              )}
              <button
                className="memory-btn memory-btn-raw"
                onClick={() => setShowRawContent(v => !v)}
              >
                <span>📋</span> {showRawContent ? '收起源文件' : '查看源文件'}
              </button>
            </div>
          </div>

          {/* 源文件折叠区域 */}
          {showRawContent && (
            <div className="memory-raw-panel">
              <div className="memory-raw-header">
                <span>{memorySubTab === 'project' ? 'project-memory.md 原始内容' : 'SOUL.md 原始内容'}</span>
                <button className="memory-raw-close" onClick={() => setShowRawContent(false)}>✕</button>
              </div>
              <div className="memory-raw-body">
                {(memorySubTab === 'project' ? projectRawContent : rawContent) ? (
                  <pre className="memory-raw-pre">{memorySubTab === 'project' ? projectRawContent : rawContent}</pre>
                ) : (
                  <div className="memory-raw-empty">暂无原始内容</div>
                )}
              </div>
            </div>
          )}

          {/* 主内容区 - 左右布局 */}
          <div className="memory-main">
            {/* 左侧分类导航 */}
            <div className="memory-sidebar">
              {(() => {
                const categoryConfig: Record<string, { icon: string; color: string }> = {
                  '用户偏好': { icon: '👤', color: '#8b5cf6' },
                  '项目规则': { icon: '📐', color: '#3b82f6' },
                  '项目规范': { icon: '📏', color: '#10b981' },
                  '工作经验': { icon: '💡', color: '#f59e0b' },
                  '工具使用经验': { icon: '🔧', color: '#ec4899' },
                  '错误教训': { icon: '⚠️', color: '#ef4444' },
                };
                const currentMemories = memorySubTab === 'project' ? projectMemories : memories;
                const currentCategories = memorySubTab === 'project' ? projectCategories : categories;
                const counts = currentMemories.reduce((acc, m) => {
                  acc[m.category] = (acc[m.category] || 0) + 1;
                  return acc;
                }, {} as Record<string, number>);
                const orderedCategories = currentCategories.length > 0 ? currentCategories : (
                  memorySubTab === 'project'
                    ? ['项目规则', '项目规范']
                    : ['用户偏好', '工作经验', '工具使用经验', '错误教训']
                );
                return (
                  <>
                    {orderedCategories.map(cat => {
                      const cfg = categoryConfig[cat] || { icon: '📄', color: '#8b5cf6' };
                      const count = counts[cat] || 0;
                      const isActive = selectedCategory === cat;
                      return (
                        <button
                          key={cat}
                          className={`memory-category-item ${isActive ? 'active' : ''}`}
                          onClick={() => setSelectedCategory(cat)}
                          style={{ '--cat-color': cfg.color } as React.CSSProperties}
                        >
                          <span className="memory-category-icon">{cfg.icon}</span>
                          <span className="memory-category-name">{cat}</span>
                          {count > 0 && (
                            <span className="memory-category-badge">{count}</span>
                          )}
                        </button>
                      );
                    })}
                    <button
                      className={`memory-category-item all ${selectedCategory === 'all' ? 'active' : ''}`}
                      onClick={() => setSelectedCategory('all')}
                    >
                      <span className="memory-category-icon">🗂️</span>
                      <span className="memory-category-name">全部</span>
                      <span className="memory-category-badge">{currentMemories.length}</span>
                    </button>
                  </>
                );
              })()}
            </div>

            {/* 右侧记忆列表 */}
            <div className="memory-content">
              {(() => {
                const categoryConfig: Record<string, { icon: string; color: string }> = {
                  '用户偏好': { icon: '👤', color: '#8b5cf6' },
                  '项目规则': { icon: '📐', color: '#3b82f6' },
                  '项目规范': { icon: '📏', color: '#10b981' },
                  '工作经验': { icon: '💡', color: '#f59e0b' },
                  '工具使用经验': { icon: '🔧', color: '#ec4899' },
                  '错误教训': { icon: '⚠️', color: '#ef4444' },
                };
                const currentMemories = memorySubTab === 'project' ? projectMemories : memories;
                const filtered = selectedCategory === 'all'
                  ? currentMemories
                  : currentMemories.filter(m => m.category === selectedCategory);

                if (filtered.length === 0) {
                  return (
                    <div className="memory-empty-state">
                      <div className="memory-empty-icon">🧠</div>
                      <div className="memory-empty-title">
                        {selectedCategory === 'all'
                          ? (memorySubTab === 'project' ? '该项目还没有记忆' : '该智能体还没有记忆')
                          : '该分类下暂无记忆'}
                      </div>
                      <div className="memory-empty-desc">
                        点击"添加"按钮开始记录新的记忆
                      </div>
                    </div>
                  );
                }

                return (
                  <div className="memory-card-list">
                    {filtered.map((item, idx) => {
                      const cfg = categoryConfig[item.category] || { icon: '📄', color: '#8b5cf6' };
                      return (
                        <div
                          key={idx}
                          className="memory-card"
                          style={{ '--card-color': cfg.color } as React.CSSProperties}
                        >
                          <div className="memory-card-border" />
                          <div className="memory-card-body">
                            <div className="memory-card-meta">
                              <span className="memory-card-category" style={{ color: cfg.color }}>
                                {cfg.icon} {item.category}
                              </span>
                              <div className="memory-card-actions">
                                <button
                                  className="memory-card-action-btn"
                                  onClick={() => {
                                    setEditingMemory(item);
                                    setEditMemoryContent(item.content);
                                    setNewMemoryCategory(item.category);
                                  }}
                                  title="编辑"
                                >
                                  ✏️
                                </button>
                                <button
                                  className="memory-card-action-btn delete"
                                  onClick={() => handleDeleteMemory(item.category, item.content)}
                                  title="删除"
                                >
                                  ✕
                                </button>
                              </div>
                            </div>
                            <div className="memory-card-text">{item.content}</div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
            </div>
          </div>

          {/* 添加记忆模态框 */}
          {showAddMemory && (
            <div className="modal-overlay" onClick={() => setShowAddMemory(false)}>
              <div className="memory-modal" onClick={e => e.stopPropagation()}>
                <h3>添加记忆</h3>
                <div className="memory-modal-body">
                  <div className="memory-form-group">
                    <label>分类</label>
                    <div className="memory-category-selector">
                      {(memorySubTab === 'project' ? projectCategories : categories).map(c => {
                        const categoryConfig: Record<string, { color: string }> = {
                          '用户偏好': { color: '#8b5cf6' },
                          '项目规则': { color: '#3b82f6' },
                          '项目规范': { color: '#10b981' },
                          '工作经验': { color: '#f59e0b' },
                          '工具使用经验': { color: '#ec4899' },
                          '错误教训': { color: '#ef4444' },
                        };
                        const cfg = categoryConfig[c] || { color: '#8b5cf6' };
                        const isSelected = newMemoryCategory === c;
                        return (
                          <button
                            key={c}
                            className={`memory-category-chip ${isSelected ? 'active' : ''}`}
                            onClick={() => setNewMemoryCategory(c)}
                            style={{
                              '--chip-color': cfg.color,
                              borderColor: isSelected ? cfg.color : undefined,
                              background: isSelected ? `${cfg.color}20` : undefined,
                              color: isSelected ? cfg.color : undefined,
                            } as React.CSSProperties}
                          >
                            {c}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  <div className="memory-form-group">
                    <label>内容</label>
                    <textarea
                      className="memory-textarea"
                      value={newMemoryContent}
                      onChange={e => setNewMemoryContent(e.target.value)}
                      placeholder="输入记忆内容..."
                      rows={5}
                    />
                  </div>
                </div>
                <div className="memory-modal-actions">
                  <button
                    className="memory-btn memory-btn-ghost"
                    onClick={() => { setShowAddMemory(false); setNewMemoryContent(''); }}
                  >
                    取消
                  </button>
                  <button
                    className="memory-btn memory-btn-primary"
                    onClick={handleAddMemory}
                    disabled={!newMemoryContent.trim()}
                  >
                    添加
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* 编辑记忆模态框 */}
          {editingMemory && (
            <div className="modal-overlay" onClick={() => setEditingMemory(null)}>
              <div className="memory-modal" onClick={e => e.stopPropagation()}>
                <h3>编辑记忆</h3>
                <div className="memory-modal-body">
                  <div className="memory-form-group">
                    <label>分类</label>
                    <div className="memory-form-value">{editingMemory.category}</div>
                  </div>
                  <div className="memory-form-group">
                    <label>内容</label>
                    <textarea
                      className="memory-textarea"
                      value={editMemoryContent}
                      onChange={e => setEditMemoryContent(e.target.value)}
                      placeholder="输入记忆内容..."
                      rows={5}
                    />
                  </div>
                </div>
                <div className="memory-modal-actions">
                  <button
                    className="memory-btn memory-btn-ghost"
                    onClick={() => { setEditingMemory(null); setEditMemoryContent(''); }}
                  >
                    取消
                  </button>
                  <button
                    className="memory-btn memory-btn-primary"
                    onClick={handleUpdateMemory}
                    disabled={!editMemoryContent.trim()}
                  >
                    保存
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SkillsManager;
