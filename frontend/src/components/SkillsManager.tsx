import React, { useState, useEffect, useCallback } from 'react';
import { skillsApi } from '../services/api';

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
      setTree(data);
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
      const content = await skillsApi.getFile(path);
      setFileContent(content);
      setEditContent(content);
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
    </div>
  );
};

export default SkillsManager;
