import React, { useState, useEffect } from 'react';
import { toolboxApi, dbConnectionApi, agentApi, taskApi } from '../services/api';

type ToolboxTab = 'files' | 'db' | 'mcp' | 'agent';

/* ================================================================
   AI工具箱主组件
   ================================================================ */
const AIToolbox: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ToolboxTab>('files');

  const tabs: { key: ToolboxTab; label: string }[] = [
    { key: 'files', label: '文件工具' },
    { key: 'db', label: '数据库连接' },
    { key: 'mcp', label: 'MCP工具' },
    { key: 'agent', label: '智能体关联' },
  ];

  return (
    <div className="ai-toolbox" style={{ maxWidth: 1200 }}>
      <div className="toolbox-tabs">
        {tabs.map(t => (
          <button
            key={t.key}
            className={`toolbox-tab ${activeTab === t.key ? 'active' : ''}`}
            onClick={() => setActiveTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === 'files' && <FileToolsPanel />}
      {activeTab === 'db' && <DbConnectionPanel />}
      {activeTab === 'mcp' && <McpToolsPanel />}
      {activeTab === 'agent' && <AgentTaskPanel />}
    </div>
  );
};

/* ================================================================
   文件工具面板
   ================================================================ */
const FileToolsPanel: React.FC = () => {
  const [searchMode, setSearchMode] = useState<'keyword' | 'search' | 'locate' | 'find'>('keyword');
  const [query, setQuery] = useState('');
  const [directory, setDirectory] = useState('');
  const [filePattern, setFilePattern] = useState('');
  const [contextLines, setContextLines] = useState(3);
  const [useRegex, setUseRegex] = useState(false);
  const [results, setResults] = useState<any[]>([]);
  const [groupedResults, setGroupedResults] = useState<Record<string, any[]>>({});
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [fileContent, setFileContent] = useState<string | null>(null);
  const [filePath, setFilePath] = useState('');
  const [viewingFile, setViewingFile] = useState(false);
  const [startLine, setStartLine] = useState<string>('');
  const [endLine, setEndLine] = useState<string>('');

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [modalPath, setModalPath] = useState('');
  const [modalContent, setModalContent] = useState('');

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setMessage(null);
    setResults([]);
    setGroupedResults({});
    try {
      let data;
      if (searchMode === 'keyword') {
        data = await toolboxApi.searchKeyword(query, directory || undefined, filePattern || undefined);
        // 按文件分组
        const grouped: Record<string, any[]> = {};
        const items = Array.isArray(data) ? data : data?.results || [];
        items.forEach((item: any) => {
          const path = item.path || item.file_path || item.filename || '未知文件';
          if (!grouped[path]) grouped[path] = [];
          grouped[path].push(item);
        });
        setGroupedResults(grouped);
        if (items.length === 0) {
          setMessage({ type: 'success', text: '搜索完成，未找到结果' });
        }
      } else if (searchMode === 'search') {
        data = await toolboxApi.searchFiles({ query, directory: directory || undefined, file_pattern: filePattern || undefined });
        setResults(Array.isArray(data) ? data : data?.results || []);
        if (!Array.isArray(data) || data.length === 0) {
          setMessage({ type: 'success', text: '搜索完成，未找到结果' });
        }
      } else if (searchMode === 'locate') {
        data = await toolboxApi.locateContent({ keyword: query, directory: directory || undefined, context_lines: contextLines });
        setResults(Array.isArray(data) ? data : data?.results || []);
        if (!Array.isArray(data) || data.length === 0) {
          setMessage({ type: 'success', text: '搜索完成，未找到结果' });
        }
      } else {
        data = await toolboxApi.findFiles({ pattern: query, directory: directory || undefined, use_regex: String(useRegex) });
        setResults(Array.isArray(data) ? data : data?.results || []);
        if (!Array.isArray(data) || data.length === 0) {
          setMessage({ type: 'success', text: '搜索完成，未找到结果' });
        }
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '搜索失败' });
    } finally {
      setLoading(false);
    }
  };

  const handleReadFile = async (path: string) => {
    setLoading(true);
    try {
      const s = startLine ? Number(startLine) : undefined;
      const e = endLine ? Number(endLine) : undefined;
      const data = await toolboxApi.readFile(path, s, e);
      setFileContent(typeof data === 'string' ? data : JSON.stringify(data, null, 2));
      setFilePath(path);
      setViewingFile(true);
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '读取文件失败' });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateFile = async () => {
    try {
      await toolboxApi.createFile({ path: modalPath, content: modalContent });
      setShowCreateModal(false);
      setModalPath('');
      setModalContent('');
      setMessage({ type: 'success', text: '文件创建成功' });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '创建失败' });
    }
  };

  const handleUpdateFile = async () => {
    try {
      await toolboxApi.updateFile({ path: modalPath, content: modalContent });
      setShowEditModal(false);
      setMessage({ type: 'success', text: '文件更新成功' });
      if (viewingFile && filePath === modalPath) {
        setFileContent(modalContent);
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '更新失败' });
    }
  };

  const handleDeleteFile = async () => {
    try {
      await toolboxApi.deleteFile(modalPath);
      setShowDeleteModal(false);
      setMessage({ type: 'success', text: '文件删除成功' });
      if (viewingFile && filePath === modalPath) {
        setViewingFile(false);
        setFileContent(null);
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '删除失败' });
    }
  };

  const openEdit = (path: string, content: string) => {
    setModalPath(path);
    setModalContent(content);
    setShowEditModal(true);
  };

  const highlightText = (text: string, keyword: string) => {
    if (!keyword.trim()) return text;
    const parts = text.split(new RegExp(`(${keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'));
    return parts.map((part, i) =>
      part.toLowerCase() === keyword.toLowerCase() ? <span key={i} className="result-highlight">{part}</span> : part
    );
  };

  return (
    <div>
      {message && (
        <div className={`toolbox-message ${message.type}`}>
          {message.text}
          <button onClick={() => setMessage(null)} style={{ marginLeft: 12, background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 16 }}>×</button>
        </div>
      )}

      <div className="toolbox-search-bar">
        <div className="search-input-group" style={{ maxWidth: 140 }}>
          <label>搜索模式</label>
          <select value={searchMode} onChange={e => setSearchMode(e.target.value as any)}>
            <option value="keyword">关键字搜索</option>
            <option value="search">全文检索</option>
            <option value="locate">关键字定位</option>
            <option value="find">文件名搜索</option>
          </select>
        </div>
        <div className="search-input-group">
          <label>{searchMode === 'find' ? '文件名模式' : searchMode === 'keyword' || searchMode === 'locate' ? '关键字' : '搜索内容'}</label>
          <input type="text" value={query} onChange={e => setQuery(e.target.value)} placeholder={searchMode === 'find' ? '*.py' : '输入内容...'} />
        </div>
        <div className="search-input-group" style={{ maxWidth: 200 }}>
          <label>目录范围</label>
          <input type="text" value={directory} onChange={e => setDirectory(e.target.value)} placeholder="/path/to/dir" />
        </div>
        {(searchMode === 'search' || searchMode === 'keyword') && (
          <div className="search-input-group" style={{ maxWidth: 160 }}>
            <label>文件类型</label>
            <input type="text" value={filePattern} onChange={e => setFilePattern(e.target.value)} placeholder="*.ts" />
          </div>
        )}
        {searchMode === 'locate' && (
          <div className="search-input-group" style={{ maxWidth: 100 }}>
            <label>上下文行</label>
            <input type="number" value={contextLines} onChange={e => setContextLines(Number(e.target.value))} min={0} max={20} />
          </div>
        )}
        {searchMode === 'find' && (
          <div className="search-input-group" style={{ maxWidth: 100, display: 'flex', alignItems: 'flex-end', paddingBottom: 10 }}>
            <label className="checkbox-label" style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-secondary)', cursor: 'pointer' }}>
              <input type="checkbox" checked={useRegex} onChange={e => setUseRegex(e.target.checked)} />
              正则
            </label>
          </div>
        )}
        <button className="btn btn-primary" onClick={handleSearch} disabled={loading || !query.trim()}>
          {loading ? '搜索中...' : '搜索'}
        </button>
        <button className="btn btn-secondary" onClick={() => { setShowCreateModal(true); setModalPath(''); setModalContent(''); }}>
          + 新建文件
        </button>
      </div>

      {viewingFile && fileContent !== null && (
        <div className="file-viewer" style={{ marginBottom: 20 }}>
          <div className="file-viewer-header">
            <span className="file-viewer-path">{filePath}</span>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>行范围:</span>
                <input type="number" value={startLine} onChange={e => setStartLine(e.target.value)} placeholder="起始" style={{ width: 70, padding: '4px 8px', fontSize: 12 }} />
                <span style={{ color: 'var(--text-secondary)' }}>-</span>
                <input type="number" value={endLine} onChange={e => setEndLine(e.target.value)} placeholder="结束" style={{ width: 70, padding: '4px 8px', fontSize: 12 }} />
                <button className="btn btn-sm btn-secondary" onClick={() => handleReadFile(filePath)}>应用</button>
              </div>
              <button className="btn btn-sm btn-secondary" onClick={() => openEdit(filePath, fileContent)}>编辑</button>
              <button className="btn btn-sm btn-danger" onClick={() => { setModalPath(filePath); setShowDeleteModal(true); }}>删除</button>
              <button className="btn btn-sm btn-secondary" onClick={() => setViewingFile(false)}>关闭</button>
            </div>
          </div>
          <div className="file-viewer-content">
            <pre><code>{fileContent}</code></pre>
          </div>
        </div>
      )}

      {/* 按文件分组的关键字搜索结果 */}
      {searchMode === 'keyword' && Object.keys(groupedResults).length > 0 && (
        <div className="search-results">
          {Object.entries(groupedResults).map(([path, items]) => (
            <div key={path} className="search-result-item">
              <div className="result-file-path" style={{ cursor: 'pointer' }} onClick={() => handleReadFile(path)}>{path}</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
                {items.map((item: any, i: number) => (
                  <span key={i} className="result-line-number" style={{ cursor: 'pointer', padding: '2px 8px', background: 'var(--glass-bg-hover)', borderRadius: 4 }} onClick={() => handleReadFile(path)}>
                    行 {item.line_number || item.line}
                  </span>
                ))}
              </div>
              {items[0]?.preview && (
                <div className="result-content" style={{ marginTop: 8 }}>
                  {highlightText(items[0].preview, query)}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {results.length > 0 && (
        <div className="search-results">
          {results.map((r, i) => (
            <div key={i} className="search-result-item" onClick={() => r.path && handleReadFile(r.path)}>
              <div className="result-file-path">{r.path || r.file_path || r.filename || '未知文件'}</div>
              {r.line_number !== undefined && <span className="result-line-number">行 {r.line_number}</span>}
              <div className="result-content">
                {typeof r.content === 'string' ? highlightText(r.content, query) : JSON.stringify(r)}
              </div>
            </div>
          ))}
        </div>
      )}

      {Object.keys(groupedResults).length === 0 && results.length === 0 && !loading && !viewingFile && !message && (
        <div className="toolbox-empty">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
          </svg>
          <p>输入搜索条件，开始文件搜索</p>
        </div>
      )}

      {loading && <div className="toolbox-loading">处理中...</div>}

      {/* 创建文件模态框 */}
      {showCreateModal && (
        <div className="toolbox-modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="toolbox-modal" onClick={e => e.stopPropagation()}>
            <h3>新建文件</h3>
            <div className="form-group">
              <label>文件路径</label>
              <input type="text" value={modalPath} onChange={e => setModalPath(e.target.value)} placeholder="/path/to/file.txt" />
            </div>
            <div className="form-group">
              <label>文件内容</label>
              <textarea value={modalContent} onChange={e => setModalContent(e.target.value)} placeholder="输入文件内容..." />
            </div>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={handleCreateFile} disabled={!modalPath.trim()}>创建</button>
              <button className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>取消</button>
            </div>
          </div>
        </div>
      )}

      {/* 编辑文件模态框 */}
      {showEditModal && (
        <div className="toolbox-modal-overlay" onClick={() => setShowEditModal(false)}>
          <div className="toolbox-modal" onClick={e => e.stopPropagation()}>
            <h3>编辑文件</h3>
            <div className="form-group">
              <label>文件路径</label>
              <input type="text" value={modalPath} readOnly />
            </div>
            <div className="form-group">
              <label>文件内容</label>
              <textarea value={modalContent} onChange={e => setModalContent(e.target.value)} />
            </div>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={handleUpdateFile}>保存</button>
              <button className="btn btn-secondary" onClick={() => setShowEditModal(false)}>取消</button>
            </div>
          </div>
        </div>
      )}

      {/* 删除确认 */}
      {showDeleteModal && (
        <div className="toolbox-modal-overlay" onClick={() => setShowDeleteModal(false)}>
          <div className="toolbox-modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 400, textAlign: 'center' }}>
            <h3>确认删除</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 20 }}>确定要删除文件 <code>{modalPath}</code> 吗？</p>
            <div className="modal-actions" style={{ justifyContent: 'center' }}>
              <button className="btn btn-danger" onClick={handleDeleteFile}>确认删除</button>
              <button className="btn btn-secondary" onClick={() => setShowDeleteModal(false)}>取消</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/* ================================================================
   数据库连接面板
   ================================================================ */
const DB_TYPES = [
  { value: 'mysql', label: 'MySQL' },
  { value: 'redis', label: 'Redis' },
  { value: 'elasticsearch', label: 'ElasticSearch' },
  { value: 'postgresql', label: 'PostgreSQL' },
  { value: 'mongodb', label: 'MongoDB' },
];

const DbConnectionPanel: React.FC = () => {
  const [connections, setConnections] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [testingId, setTestingId] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<any>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);

  const [form, setForm] = useState({
    name: '', db_type: 'mysql', host: '', port: 3306,
    username: '', password: '', database_name: '', extra_params: '{}',
  });

  useEffect(() => { loadConnections(); }, []);

  const loadConnections = async () => {
    setLoading(true);
    try {
      const data = await dbConnectionApi.list();
      setConnections(data);
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '加载失败' });
    } finally {
      setLoading(false);
    }
  };

  const openCreate = () => {
    setEditingId(null);
    setForm({ name: '', db_type: 'mysql', host: '', port: 3306, username: '', password: '', database_name: '', extra_params: '{}' });
    setShowModal(true);
  };

  const openEdit = (conn: any) => {
    setEditingId(conn.id);
    setForm({
      name: conn.name || '', db_type: conn.db_type || 'mysql',
      host: conn.host || '', port: conn.port || 3306,
      username: conn.username || '', password: '',
      database_name: conn.database_name || '',
      extra_params: JSON.stringify(conn.extra_params || {}),
    });
    setShowModal(true);
  };

  const handleSave = async () => {
    try {
      const payload: any = {
        ...form,
        extra_params: JSON.parse(form.extra_params || '{}'),
      };
      if (editingId) {
        await dbConnectionApi.update(editingId, payload);
      } else {
        await dbConnectionApi.create(payload);
      }
      setShowModal(false);
      loadConnections();
      setMessage({ type: 'success', text: editingId ? '连接已更新' : '连接已创建' });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '保存失败' });
    }
  };

  const handleTest = async (id: number) => {
    setTestingId(id);
    setTestResult(null);
    try {
      const res = await dbConnectionApi.test(id);
      setTestResult({ id, success: true, data: res });
    } catch (err: any) {
      setTestResult({ id, success: false, error: err.message || '测试失败' });
    } finally {
      setTestingId(null);
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await dbConnectionApi.delete(deleteId);
      setDeleteId(null);
      loadConnections();
      setMessage({ type: 'success', text: '连接已删除' });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '删除失败' });
    }
  };

  const isRedis = form.db_type === 'redis';

  return (
    <div>
      {message && (
        <div className={`toolbox-message ${message.type}`}>
          {message.text}
          <button onClick={() => setMessage(null)} style={{ marginLeft: 12, background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 16 }}>×</button>
        </div>
      )}

      <div style={{ marginBottom: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-primary)' }}>数据库连接</h3>
        <button className="btn btn-primary" onClick={openCreate}>+ 新建连接</button>
      </div>

      {connections.length === 0 && !loading && (
        <div className="toolbox-empty">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <ellipse cx="12" cy="5" rx="9" ry="3" />
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
          </svg>
          <p>暂无数据库连接，点击上方按钮添加</p>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {connections.map(conn => (
          <div key={conn.id} className="db-connection-card">
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                <span className={`db-type-badge ${conn.db_type}`}>{conn.db_type}</span>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{conn.name}</span>
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                {conn.host}:{conn.port}
                {conn.database_name && ` / ${conn.database_name}`}
              </div>
              {testResult && testResult.id === conn.id && (
                <div style={{ marginTop: 8, fontSize: 13 }}>
                  {testResult.success ? (
                    <span className="status-badge success">连接成功</span>
                  ) : (
                    <span className="status-badge error">连接失败: {testResult.error}</span>
                  )}
                </div>
              )}
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button className="btn btn-sm btn-secondary" onClick={() => handleTest(conn.id)} disabled={testingId === conn.id}>
                {testingId === conn.id ? '测试中...' : '测试'}
              </button>
              <button className="btn btn-sm btn-secondary" onClick={() => openEdit(conn)}>编辑</button>
              <button className="btn btn-sm btn-danger" onClick={() => setDeleteId(conn.id)}>删除</button>
            </div>
          </div>
        ))}
      </div>

      {loading && <div className="toolbox-loading">加载中...</div>}

      {/* 新建/编辑模态框 */}
      {showModal && (
        <div className="toolbox-modal-overlay" onClick={() => setShowModal(false)}>
          <div className="toolbox-modal" onClick={e => e.stopPropagation()}>
            <h3>{editingId ? '编辑连接' : '新建连接'}</h3>
            <div className="form-group">
              <label>数据库类型</label>
              <select value={form.db_type} onChange={e => setForm(p => ({ ...p, db_type: e.target.value }))}>
                {DB_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>连接名称</label>
              <input type="text" value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="例如：生产MySQL" />
            </div>
            <div className="form-group">
              <label>主机</label>
              <input type="text" value={form.host} onChange={e => setForm(p => ({ ...p, host: e.target.value }))} placeholder="localhost" />
            </div>
            <div className="form-group">
              <label>端口</label>
              <input type="number" value={form.port} onChange={e => setForm(p => ({ ...p, port: Number(e.target.value) }))} />
            </div>
            {!isRedis && (
              <>
                <div className="form-group">
                  <label>用户名</label>
                  <input type="text" value={form.username} onChange={e => setForm(p => ({ ...p, username: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label>数据库名</label>
                  <input type="text" value={form.database_name} onChange={e => setForm(p => ({ ...p, database_name: e.target.value }))} />
                </div>
              </>
            )}
            <div className="form-group">
              <label>密码</label>
              <input type="password" value={form.password} onChange={e => setForm(p => ({ ...p, password: e.target.value }))} placeholder={editingId ? '留空则不修改' : ''} />
            </div>
            <div className="form-group">
              <label>额外参数 (JSON)</label>
              <input type="text" value={form.extra_params} onChange={e => setForm(p => ({ ...p, extra_params: e.target.value }))} placeholder='{"ssl": true}' />
            </div>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={handleSave} disabled={!form.name.trim() || !form.host.trim()}>保存</button>
              <button className="btn btn-secondary" onClick={() => setShowModal(false)}>取消</button>
            </div>
          </div>
        </div>
      )}

      {/* 删除确认 */}
      {deleteId && (
        <div className="toolbox-modal-overlay" onClick={() => setDeleteId(null)}>
          <div className="toolbox-modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 400, textAlign: 'center' }}>
            <h3>确认删除</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 20 }}>确定要删除此数据库连接吗？</p>
            <div className="modal-actions" style={{ justifyContent: 'center' }}>
              <button className="btn btn-danger" onClick={handleDelete}>确认删除</button>
              <button className="btn btn-secondary" onClick={() => setDeleteId(null)}>取消</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/* ================================================================
   MCP工具面板
   ================================================================ */
const McpToolsPanel: React.FC = () => {
  const [tools, setTools] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [expandedTool, setExpandedTool] = useState<string | null>(null);
  const [paramValues, setParamValues] = useState<Record<string, any>>({});
  const [executeResult, setExecuteResult] = useState<any>(null);
  const [executing, setExecuting] = useState(false);
  const [confirmTool, setConfirmTool] = useState<{ name: string; params: Record<string, any> } | null>(null);

  useEffect(() => {
    loadTools();
  }, []);

  const loadTools = async () => {
    setLoading(true);
    try {
      const data = await toolboxApi.getMcpTools();
      setTools(Array.isArray(data) ? data : data?.tools || []);
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '获取MCP工具失败' });
    } finally {
      setLoading(false);
    }
  };

  const doExecute = async (toolName: string, params: Record<string, any>) => {
    setExecuting(true);
    setExecuteResult(null);
    try {
      const start = Date.now();
      const res = await toolboxApi.executeMcpTool({ tool_name: toolName, parameters: params });
      setExecuteResult({ success: true, data: res, elapsed: Date.now() - start });
    } catch (err: any) {
      setExecuteResult({ success: false, error: err.message || '执行失败' });
    } finally {
      setExecuting(false);
    }
  };

  const handleExecuteClick = (tool: any, params: Record<string, any>) => {
    if (tool.requires_confirmation) {
      setConfirmTool({ name: tool.name, params });
      return;
    }
    doExecute(tool.name, params);
  };

  const isTerminalTool = (toolName: string) => toolName === 'terminal_execute';

  const isBrowserTool = (toolName: string) =>
    toolName.startsWith('browser_') || toolName === 'browser_navigate' || toolName === 'browser_screenshot'
    || toolName === 'browser_click' || toolName === 'browser_type' || toolName === 'browser_extract';

  const renderTerminalResult = (data: any) => {
    const stdout = data?.stdout || data?.output || '';
    const stderr = data?.stderr || '';
    const exitCode = data?.exit_code ?? data?.returncode;
    return (
      <div>
        {exitCode !== undefined && (
          <div style={{ marginBottom: 8, fontSize: 12, fontFamily: 'SF Mono, monospace' }}>
            <span style={{ color: exitCode === 0 ? '#10B981' : '#EF4444' }}>
              Exit code: {exitCode}
            </span>
          </div>
        )}
        {stdout && (
          <div className="terminal-output">
            <div className="terminal-output-label">stdout</div>
            <pre>{stdout}</pre>
          </div>
        )}
        {stderr && (
          <div className="terminal-output terminal-output-stderr">
            <div className="terminal-output-label">stderr</div>
            <pre>{stderr}</pre>
          </div>
        )}
        {!stdout && !stderr && <pre>{JSON.stringify(data, null, 2)}</pre>}
      </div>
    );
  };

  const renderBrowserResult = (data: any) => {
    const screenshot = data?.screenshot || data?.image;
    const url = data?.url;
    return (
      <div>
        {url && (
          <div style={{ marginBottom: 8, fontSize: 12, fontFamily: 'SF Mono, monospace' }}>
            <span style={{ color: 'var(--color-primary-2)' }}>URL: {url}</span>
          </div>
        )}
        {screenshot && (
          <div style={{ marginBottom: 12 }}>
            <img
              src={screenshot.startsWith('data:') ? screenshot : `data:image/png;base64,${screenshot}`}
              alt="截图"
              style={{ maxWidth: '100%', borderRadius: 8, border: '1px solid var(--glass-border)' }}
            />
          </div>
        )}
        {data?.content && (
          <div className="terminal-output">
            <div className="terminal-output-label">提取内容</div>
            <pre>{typeof data.content === 'string' ? data.content : JSON.stringify(data.content, null, 2)}</pre>
          </div>
        )}
        {!screenshot && !data?.content && !url && <pre>{JSON.stringify(data, null, 2)}</pre>}
      </div>
    );
  };

  return (
    <div>
      {message && (
        <div className={`toolbox-message ${message.type}`}>
          {message.text}
          <button onClick={() => setMessage(null)} style={{ marginLeft: 12, background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 16 }}>×</button>
        </div>
      )}

      {tools.length === 0 && !loading && (
        <div className="toolbox-empty">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
          </svg>
          <p>暂无MCP工具可用</p>
        </div>
      )}

      <div className="mcp-tools-grid">
        {tools.map((tool, idx) => {
          const isExpanded = expandedTool === (tool.name || idx);
          const parameters = tool.parameters?.properties || tool.parameters || {};
          const required = tool.parameters?.required || [];
          const isTerminal = isTerminalTool(tool.name);
          const isBrowser = isBrowserTool(tool.name);
          return (
            <div key={idx} className={`mcp-tool-card ${isExpanded ? 'expanded' : ''}`} onClick={() => {
              if (!isExpanded) {
                setExpandedTool(tool.name || idx);
                setParamValues({});
                setExecuteResult(null);
              }
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <div className="tool-name">{tool.name}</div>
                {tool.category && <span className="tool-category-badge">{tool.category}</span>}
                {isTerminal && <span className="tool-category-badge" style={{ background: 'rgba(16,185,129,0.2)', color: '#10B981' }}>终端</span>}
                {isBrowser && <span className="tool-category-badge" style={{ background: 'rgba(59,130,246,0.2)', color: '#3B82F6' }}>Browser</span>}
                {tool.requires_confirmation && <span className="tool-confirmation-badge">需确认</span>}
              </div>
              <div className="tool-description">{tool.description || '无描述'}</div>
              {Object.keys(parameters).length > 0 && !isExpanded && (
                <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                  参数: {Object.keys(parameters).join(', ')}
                </div>
              )}

              {isExpanded && (
                <div className="tool-execute-panel">
                  <div className="tool-param-form">
                    {Object.entries(parameters).map(([key, schema]: [string, any]) => (
                      <div key={key} className="tool-param-item">
                        <label>{key} {required.includes(key) && <span style={{ color: '#EF4444' }}>*</span>}</label>
                        {isTerminal && key === 'command' ? (
                          <textarea
                            placeholder={schema.description || ''}
                            value={paramValues[key] || ''}
                            onChange={e => setParamValues(p => ({ ...p, [key]: e.target.value }))}
                            rows={3}
                            style={{ fontFamily: 'SF Mono, monospace', fontSize: 13 }}
                          />
                        ) : isBrowser && key === 'url' ? (
                          <input
                            type="url"
                            placeholder={schema.description || 'https://...'}
                            value={paramValues[key] || ''}
                            onChange={e => setParamValues(p => ({ ...p, [key]: e.target.value }))}
                          />
                        ) : isBrowser && (key === 'text' || key === 'selector') ? (
                          <input
                            type="text"
                            placeholder={schema.description || ''}
                            value={paramValues[key] || ''}
                            onChange={e => setParamValues(p => ({ ...p, [key]: e.target.value }))}
                          />
                        ) : (
                          <input
                            type={schema.type === 'integer' || key === 'timeout' || key === 'wait_after' ? 'number' : 'text'}
                            placeholder={schema.description || ''}
                            value={paramValues[key] || ''}
                            onChange={e => setParamValues(p => ({ ...p, [key]: e.target.value }))}
                          />
                        )}
                      </div>
                    ))}
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <button className="btn btn-primary" onClick={e => { e.stopPropagation(); handleExecuteClick(tool, paramValues); }} disabled={executing}>
                      {executing ? '执行中...' : (tool.requires_confirmation ? '执行 (需确认)' : '执行')}
                    </button>
                    <button className="btn btn-secondary" onClick={e => { e.stopPropagation(); setExpandedTool(null); }}>收起</button>
                  </div>

                  {executeResult && (
                    <div className="tool-result">
                      <div style={{ marginBottom: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
                        {executeResult.success ? (
                          <span className="status-badge success">成功</span>
                        ) : (
                          <span className="status-badge error">失败</span>
                        )}
                        {executeResult.elapsed !== undefined && (
                          <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{executeResult.elapsed}ms</span>
                        )}
                      </div>
                      {executeResult.success && isTerminal ? (
                        renderTerminalResult(executeResult.data)
                      ) : executeResult.success && isBrowser ? (
                        renderBrowserResult(executeResult.data)
                      ) : (
                        <pre>{executeResult.success ? JSON.stringify(executeResult.data, null, 2) : executeResult.error}</pre>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {loading && <div className="toolbox-loading">加载中...</div>}

      {/* 执行确认弹窗 */}
      {confirmTool && (
        <div className="toolbox-modal-overlay" onClick={() => setConfirmTool(null)}>
          <div className="toolbox-modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 500 }}>
            <h3>确认执行</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 16 }}>
              工具 <strong>{confirmTool.name}</strong> 需要确认才能执行。确定要继续吗？
            </p>
            {Object.keys(confirmTool.params).length > 0 && (
              <div style={{ marginBottom: 16, padding: 12, background: 'var(--glass-bg)', borderRadius: 8, border: '1px solid var(--glass-border)' }}>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>参数：</div>
                <pre style={{ margin: 0, fontSize: 12, fontFamily: 'SF Mono, monospace' }}>
                  {JSON.stringify(confirmTool.params, null, 2)}
                </pre>
              </div>
            )}
            <div className="modal-actions" style={{ justifyContent: 'center' }}>
              <button className="btn btn-primary" onClick={() => { doExecute(confirmTool.name, confirmTool.params); setConfirmTool(null); }}>确认执行</button>
              <button className="btn btn-secondary" onClick={() => setConfirmTool(null)}>取消</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/* ================================================================
   智能体关联面板
   ================================================================ */
const AgentTaskPanel: React.FC = () => {
  const [agents, setAgents] = useState<any[]>([]);
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);
  const [taskName, setTaskName] = useState('');
  const [taskDescription, setTaskDescription] = useState('');
  const [priority, setPriority] = useState(1);
  const [suggesting, setSuggesting] = useState(false);

  const [modifyTaskId, setModifyTaskId] = useState<number | null>(null);
  const [modifyPrompt, setModifyPrompt] = useState('');
  const [statusTaskId, setStatusTaskId] = useState<number | null>(null);
  const [taskStatus, setTaskStatus] = useState<any>(null);

  useEffect(() => {
    loadAgents();
    loadTasks();
  }, []);

  const loadAgents = async () => {
    try {
      const data = await agentApi.getAgents();
      setAgents(data);
      if (data.length > 0 && !selectedAgentId) {
        setSelectedAgentId(data[0].id);
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '加载智能体失败' });
    }
  };

  const loadTasks = async () => {
    setLoading(true);
    try {
      const data = await taskApi.getTasks();
      setTasks(data);
    } catch (err: any) {
      //  toolbox 相关的任务可能不在普通任务列表中，静默失败
    } finally {
      setLoading(false);
    }
  };

  const handleSuggest = async () => {
    if (!selectedAgentId || !taskName.trim() || !taskDescription.trim()) return;
    setSuggesting(true);
    try {
      const res = await toolboxApi.suggestTask({
        agent_id: selectedAgentId,
        task_name: taskName,
        task_description: taskDescription,
        priority,
      });
      setTaskName('');
      setTaskDescription('');
      setPriority(1);
      setMessage({ type: 'success', text: `任务建议已提交 (ID: ${res.id || 'unknown'})` });
      loadTasks();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '提交失败' });
    } finally {
      setSuggesting(false);
    }
  };

  const handleConfirm = async (id: number) => {
    try {
      await toolboxApi.confirmTask(id);
      setMessage({ type: 'success', text: '任务已确认执行' });
      loadTasks();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '确认失败' });
    }
  };

  const handleModify = async () => {
    if (!modifyTaskId) return;
    try {
      await toolboxApi.modifyTask(modifyTaskId, { modification_prompt: modifyPrompt });
      setModifyTaskId(null);
      setModifyPrompt('');
      setMessage({ type: 'success', text: '修改请求已提交' });
      loadTasks();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '修改失败' });
    }
  };

  const handleGetStatus = async (id: number) => {
    try {
      const res = await toolboxApi.getTaskStatus(id);
      setStatusTaskId(id);
      setTaskStatus(res);
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '获取状态失败' });
    }
  };

  const statusClass = (status: string) => {
    const map: Record<string, string> = {
      pending_confirmation: 'pending_confirmation',
      confirmed: 'confirmed',
      running: 'running',
      completed: 'completed',
      failed: 'failed',
    };
    return map[status] || 'info';
  };

  return (
    <div>
      {message && (
        <div className={`toolbox-message ${message.type}`}>
          {message.text}
          <button onClick={() => setMessage(null)} style={{ marginLeft: 12, background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 16 }}>×</button>
        </div>
      )}

      <div className="card glass" style={{ padding: 20, marginBottom: 20 }}>
        <h4 style={{ margin: '0 0 16px 0', fontSize: '1rem', color: 'var(--text-primary)' }}>创建任务建议</h4>
        <div className="form-group">
          <label className="form-label">选择智能体</label>
          <select className="input" value={selectedAgentId ?? ''} onChange={e => setSelectedAgentId(Number(e.target.value))}>
            {agents.map(a => <option key={a.id} value={a.id}>{a.name || `Agent #${a.id}`}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">任务名称</label>
          <input className="input" type="text" value={taskName} onChange={e => setTaskName(e.target.value)} placeholder="任务名称" />
        </div>
        <div className="form-group">
          <label className="form-label">任务描述</label>
          <textarea className="input" value={taskDescription} onChange={e => setTaskDescription(e.target.value)} placeholder="描述任务内容..." rows={3} style={{ resize: 'vertical' }} />
        </div>
        <div className="form-group">
          <label className="form-label">优先级 (1-5)</label>
          <input className="input" type="number" min={1} max={5} value={priority} onChange={e => setPriority(Number(e.target.value))} />
        </div>
        <button className="btn btn-primary" onClick={handleSuggest} disabled={suggesting || !taskName.trim() || !taskDescription.trim() || !selectedAgentId}>
          {suggesting ? '提交中...' : '建议创建任务'}
        </button>
      </div>

      <h4 style={{ margin: '0 0 16px 0', fontSize: '1rem', color: 'var(--text-primary)' }}>任务列表</h4>
      {tasks.length === 0 && !loading && (
        <div className="toolbox-empty">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M9 11l3 3L22 4" />
            <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
          </svg>
          <p>暂无任务</p>
        </div>
      )}

      <div>
        {tasks.map(task => (
          <div key={task.id} className="agent-task-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
              <div>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>{task.name || task.task_name}</div>
                <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{task.description || task.task_description}</div>
              </div>
              <span className={`task-status-badge ${statusClass(task.status)}`}>{task.status}</span>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              {task.status === 'pending_confirmation' && (
                <button className="btn btn-sm btn-primary" onClick={() => handleConfirm(task.id)}>确认执行</button>
              )}
              <button className="btn btn-sm btn-secondary" onClick={() => { setModifyTaskId(task.id); setModifyPrompt(''); }}>修改</button>
              <button className="btn btn-sm btn-secondary" onClick={() => handleGetStatus(task.id)}>查看状态</button>
            </div>

            {statusTaskId === task.id && taskStatus && (
              <div className="task-detail-panel" style={{ marginTop: 12 }}>
                <h4>任务状态</h4>
                <pre style={{ fontSize: 13, fontFamily: 'SF Mono, monospace', whiteSpace: 'pre-wrap' }}>{JSON.stringify(taskStatus, null, 2)}</pre>
              </div>
            )}
          </div>
        ))}
      </div>

      {loading && <div className="toolbox-loading">加载中...</div>}

      {/* 修改模态框 */}
      {modifyTaskId && (
        <div className="toolbox-modal-overlay" onClick={() => setModifyTaskId(null)}>
          <div className="toolbox-modal" onClick={e => e.stopPropagation()}>
            <h3>修改任务</h3>
            <div className="form-group">
              <label>修改指令（自然语言）</label>
              <textarea value={modifyPrompt} onChange={e => setModifyPrompt(e.target.value)} placeholder="例如：将优先级提高到5，增加执行超时时间..." rows={4} />
            </div>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={handleModify} disabled={!modifyPrompt.trim()}>提交修改</button>
              <button className="btn btn-secondary" onClick={() => setModifyTaskId(null)}>取消</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AIToolbox;
