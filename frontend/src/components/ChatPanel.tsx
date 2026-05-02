import React, { useState, useEffect, useRef } from 'react';
import { chatApi, environmentApi, authApi } from '../services/api';

interface ChatConfig {
  id: number;
  name: string;
  vendor: string;
  model_name: string;
  model_list?: string[];
  is_default: boolean;
}

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

interface UserProfile {
  id: number;
  username: string;
  email: string;
  avatar?: string;
}

const VENDOR_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  azure: 'Azure',
  xiaomi: '小米',
  custom: '自定义',
};

const ChatPanel: React.FC = () => {
  const [configs, setConfigs] = useState<ChatConfig[]>([]);
  const [selectedConfigId, setSelectedConfigId] = useState<number | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [workingDirectory, setWorkingDirectory] = useState<string>('');
  const [envSummary, setEnvSummary] = useState<string>('');
  const [user, setUser] = useState<UserProfile | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => { loadConfigs(); }, []);

  useEffect(() => {
    authApi.getProfile().then(data => setUser(data)).catch(() => {});
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    const savedDir = localStorage.getItem('chat_working_directory');
    const savedEnv = localStorage.getItem('chat_env_summary');
    if (savedDir) {
      setWorkingDirectory(savedDir);
      if (savedEnv) {
        setEnvSummary(savedEnv);
      } else {
        // 自动检测
        environmentApi.getSummary(savedDir).then(result => {
          setEnvSummary(result.summary);
          localStorage.setItem('chat_env_summary', result.summary);
        }).catch(() => {});
      }
    }
  }, []);

  const loadConfigs = async () => {
    try {
      const data = await chatApi.getConfigs();
      setConfigs(data);
      if (data.length > 0 && !selectedConfigId) {
        const def = data.find(c => c.is_default) || data[0];
        setSelectedConfigId(def.id);
        setSelectedModel(def.model_list?.[0] || def.model_name);
      }
    } catch (err: any) {
      setError(err.message || '加载模型列表失败');
    }
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading || !selectedConfigId) return;

    const userMsg: Message = { role: 'user', content: text };
    const updated = [...messages, userMsg];
    setMessages(updated);
    setInput('');
    setError(null);
    setLoading(true);

    try {
      const systemContent = [
        `用户的工作目录为: ${workingDirectory}，所有文件操作限制在此目录内。`,
        envSummary ? `\n用户设备环境信息:\n${envSummary}\n请根据以上环境信息生成兼容的终端命令。` : ''
      ].join('');

      const apiMessages = [
        { role: 'system' as const, content: systemContent },
        ...updated.map(m => ({ role: m.role, content: m.content })),
      ];
      const res = await chatApi.sendMessage(selectedConfigId, apiMessages, selectedModel);
      setMessages([...updated, { role: 'assistant', content: res.reply }]);
    } catch (err: any) {
      setError(err.message || '对话请求失败');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const selectedConfig = configs.find(c => c.id === selectedConfigId);
  const selectValue = selectedConfigId && selectedModel
    ? `${selectedConfigId}:${selectedModel}`
    : '';

  const handleModelSelect = (value: string) => {
    const idx = value.indexOf(':');
    if (idx > 0) {
      setSelectedConfigId(Number(value.slice(0, idx)));
      setSelectedModel(value.slice(idx + 1));
    }
  };

  return (
    <div className="chat-panel">
      {/* 顶部模型选择 */}
      <div className="chat-header">
        <div className="chat-model-selector">
          <label className="form-label" style={{ marginBottom: 0, whiteSpace: 'nowrap' }}>模型：</label>
          <select
            className="input"
            value={selectValue}
            onChange={e => handleModelSelect(e.target.value)}
            style={{ maxWidth: 360 }}
          >
            {configs.length === 0 && <option value="">暂无可用模型</option>}
            {configs.map(c => {
              const models = c.model_list && c.model_list.length > 0 ? c.model_list : [c.model_name];
              return models.map(m => (
                <option key={`${c.id}:${m}`} value={`${c.id}:${m}`}>
                  {c.name} / {m} ({VENDOR_LABELS[c.vendor] || c.vendor})
                </option>
              ));
            })}
          </select>
        </div>
        {selectedConfig && (
          <span className="chat-model-badge">
            {VENDOR_LABELS[selectedConfig.vendor] || selectedConfig.vendor}
          </span>
        )}
        <div className="working-directory-indicator" style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 12px',
          background: 'var(--glass-bg)',
          borderRadius: 'var(--radius-btn)',
          border: '1px solid var(--glass-border)',
          fontSize: '12px',
          color: 'var(--text-secondary)',
          marginLeft: 'auto',
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          <span style={{ fontFamily: "'SF Mono', monospace", color: 'var(--color-primary-2)' }}>
            {workingDirectory}
          </span>
          {envSummary && (
            <span title="环境信息已加载" style={{
              display: 'inline-flex', alignItems: 'center', gap: '4px',
              fontSize: '11px', color: 'var(--color-primary-3)', marginLeft: '8px'
            }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
              </svg>
              环境已检测
            </span>
          )}
        </div>
      </div>

      {/* 消息列表 */}
          <div className="chat-messages">
            {messages.length === 0 && (
              <div className="chat-empty">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.3">
                  <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
                </svg>
                <p>开始与 AI 对话</p>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>在下方输入消息，选择上方模型开始对话</p>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`chat-message chat-message-${m.role}`}>
                <div className="chat-message-avatar">
                  {m.role === 'user' ? (
                    user?.avatar ? (
                      <div className="avatar-circle avatar-small">
                        <img src={user.avatar} alt="用户头像" />
                      </div>
                    ) : (
                      <div className="avatar-circle avatar-small avatar-default">
                        <span>{user?.username?.charAt(0).toUpperCase() || 'U'}</span>
                      </div>
                    )
                  ) : (
                    <div className="avatar-circle avatar-small" style={{ background: 'linear-gradient(135deg, rgba(6,182,212,0.15), rgba(16,185,129,0.1))' }}>
                      <span style={{ fontSize: '1rem' }}>🤖</span>
                    </div>
                  )}
                </div>
                <div className="chat-message-bubble">
                  {m.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="chat-message chat-message-assistant">
                <div className="chat-message-avatar">
                  <div className="avatar-circle avatar-small" style={{ background: 'linear-gradient(135deg, rgba(6,182,212,0.15), rgba(16,185,129,0.1))' }}>
                    <span style={{ fontSize: '1rem' }}>🤖</span>
                  </div>
                </div>
                <div className="chat-message-bubble chat-loading">
                  <span className="dot-pulse" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* 错误提示 */}
          {error && (
            <div className="chat-error">
              <span>{error}</span>
              <button onClick={() => setError(null)}>×</button>
            </div>
          )}

          {/* 输入栏 */}
          <div className="chat-input-bar">
            <textarea
              className="chat-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入消息，Enter 发送，Shift+Enter 换行"
              rows={2}
              disabled={loading || !selectedConfigId}
            />
            <button
              className="btn btn-primary chat-send-btn"
              onClick={handleSend}
              disabled={loading || !input.trim() || !selectedConfigId}
            >
              {loading ? '发送中...' : '发送'}
            </button>
          </div>
    </div>
  );
};

export default ChatPanel;
