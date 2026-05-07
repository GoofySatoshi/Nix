import React, { useState, useEffect } from 'react';
import { coreApi } from '../services/api';

interface AgentInfo {
  id: string;
  name: string;
  description: string;
  status: string;
  capabilities: string;
  memory_size: number;
}

interface ToolInfo {
  name: string;
  description: string;
  category: string;
  dangerous: boolean;
}

interface ContextSnapshot {
  tasks: Record<string, any>;
  agents: Record<string, any>;
  global_keys: string[];
  project_info: any;
}

export default function CoreDashboard() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [context, setContext] = useState<ContextSnapshot | null>(null);
  const [messageHistory, setMessageHistory] = useState<any[]>([]);
  const [orchestrateInput, setOrchestrateInput] = useState('');
  const [orchestrateResult, setOrchestrateResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'agents' | 'tools' | 'context' | 'messages' | 'orchestrate'>('agents');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [agentsData, toolsData, contextData, msgsData] = await Promise.all([
        coreApi.listAgents().catch(() => []),
        coreApi.listTools().catch(() => []),
        coreApi.getContextSnapshot().catch(() => null),
        coreApi.getMessageHistory(undefined, 20).catch(() => []),
      ]);
      setAgents(agentsData);
      setTools(toolsData);
      setContext(contextData);
      setMessageHistory(msgsData);
    } catch (e) {
      console.error('加载核心数据失败:', e);
    }
  };

  const handleOrchestrate = async () => {
    if (!orchestrateInput.trim()) return;
    setLoading(true);
    try {
      const result = await coreApi.orchestrate(orchestrateInput);
      setOrchestrateResult(result);
      loadData(); // 刷新状态
    } catch (e: any) {
      setOrchestrateResult({ error: e.message });
    } finally {
      setLoading(false);
    }
  };

  const handleToggleAgent = async (agentId: string, currentStatus: string) => {
    try {
      if (currentStatus === 'stopped') {
        await coreApi.startAgent(agentId);
      } else {
        await coreApi.stopAgent(agentId);
      }
      loadData();
    } catch (e: any) {
      alert(`操作失败: ${e.message}`);
    }
  };

  const tabs = [
    { key: 'agents', label: '🤖 智能体', count: agents.length },
    { key: 'tools', label: '🔧 工具', count: tools.length },
    { key: 'context', label: '📊 上下文', count: context ? Object.keys(context.agents).length : 0 },
    { key: 'messages', label: '💬 消息', count: messageHistory.length },
    { key: 'orchestrate', label: '🎯 编排', count: null },
  ] as const;

  return (
    <div style={{ padding: '20px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: '16px' }}>
        <h2 style={{ margin: '0 0 8px', color: 'var(--text-primary)' }}>核心架构监控</h2>
        <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '14px' }}>
          新架构 Agent 系统运行状态
        </p>
      </div>

      {/* Tab 导航 */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', flexWrap: 'wrap' }}>
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              border: activeTab === tab.key ? '2px solid var(--color-primary-1)' : '1px solid var(--glass-border)',
              background: activeTab === tab.key ? 'var(--color-primary-1)' : 'var(--glass-bg)',
              color: activeTab === tab.key ? 'white' : 'var(--text-primary)',
              cursor: 'pointer',
              fontSize: '14px',
            }}
          >
            {tab.label}
            {tab.count !== null && (
              <span style={{ marginLeft: '6px', opacity: 0.7 }}>({tab.count})</span>
            )}
          </button>
        ))}
        <button
          onClick={loadData}
          style={{
            padding: '8px 16px',
            borderRadius: '8px',
            border: '1px solid var(--glass-border)',
            background: 'var(--glass-bg)',
            color: 'var(--text-primary)',
            cursor: 'pointer',
            fontSize: '14px',
            marginLeft: 'auto',
          }}
        >
          🔄 刷新
        </button>
      </div>

      {/* 内容区 */}
      <div style={{
        flex: 1,
        background: 'var(--glass-bg)',
        borderRadius: '12px',
        border: '1px solid var(--glass-border)',
        padding: '16px',
        overflowY: 'auto',
      }}>
        {/* Agent 列表 */}
        {activeTab === 'agents' && (
          <div>
            <h3 style={{ margin: '0 0 12px', color: 'var(--text-primary)' }}>智能体列表</h3>
            {agents.length === 0 ? (
              <p style={{ color: 'var(--text-secondary)' }}>暂无智能体</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {agents.map(agent => (
                  <div key={agent.id} style={{
                    padding: '12px',
                    borderRadius: '8px',
                    border: '1px solid var(--glass-border)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}>
                    <div>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                        {agent.name}
                        <span style={{
                          marginLeft: '8px',
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontSize: '12px',
                          background: agent.status === 'idle' ? '#10b981' : agent.status === 'busy' ? '#f59e0b' : '#6b7280',
                          color: 'white',
                        }}>
                          {agent.status}
                        </span>
                      </div>
                      <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                        {agent.description} | 能力: {agent.capabilities} | 记忆: {agent.memory_size}条
                      </div>
                    </div>
                    <button
                      onClick={() => handleToggleAgent(agent.id, agent.status)}
                      style={{
                        padding: '6px 12px',
                        borderRadius: '6px',
                        border: 'none',
                        background: agent.status === 'stopped' ? '#10b981' : '#ef4444',
                        color: 'white',
                        cursor: 'pointer',
                        fontSize: '13px',
                      }}
                    >
                      {agent.status === 'stopped' ? '启动' : '停止'}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 工具列表 */}
        {activeTab === 'tools' && (
          <div>
            <h3 style={{ margin: '0 0 12px', color: 'var(--text-primary)' }}>工具注册表</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '8px' }}>
              {tools.map(tool => (
                <div key={tool.name} style={{
                  padding: '10px',
                  borderRadius: '8px',
                  border: `1px solid ${tool.dangerous ? '#ef4444' : 'var(--glass-border)'}`,
                }}>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                    {tool.name}
                    {tool.dangerous && <span style={{ marginLeft: '6px', color: '#ef4444', fontSize: '12px' }}>⚠️危险</span>}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    [{tool.category}] {tool.description}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 上下文快照 */}
        {activeTab === 'context' && context && (
          <div>
            <h3 style={{ margin: '0 0 12px', color: 'var(--text-primary)' }}>共享上下文</h3>
            <pre style={{
              padding: '12px',
              borderRadius: '8px',
              background: 'var(--bg-secondary)',
              fontSize: '13px',
              overflow: 'auto',
              color: 'var(--text-primary)',
            }}>
              {JSON.stringify(context, null, 2)}
            </pre>
          </div>
        )}

        {/* 消息历史 */}
        {activeTab === 'messages' && (
          <div>
            <h3 style={{ margin: '0 0 12px', color: 'var(--text-primary)' }}>消息总线历史</h3>
            {messageHistory.length === 0 ? (
              <p style={{ color: 'var(--text-secondary)' }}>暂无消息</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {messageHistory.map((msg, i) => (
                  <div key={i} style={{
                    padding: '8px',
                    borderRadius: '6px',
                    fontSize: '13px',
                    fontFamily: 'monospace',
                    background: 'var(--bg-secondary)',
                    color: 'var(--text-primary)',
                  }}>
                    <span style={{ color: 'var(--color-primary-1)' }}>[{msg.type}]</span>{' '}
                    <span style={{ color: '#10b981' }}>{msg.from}</span>
                    {msg.to && <> → <span style={{ color: '#f59e0b' }}>{msg.to}</span></>}
                    {' '}({msg.timestamp})
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 任务编排 */}
        {activeTab === 'orchestrate' && (
          <div>
            <h3 style={{ margin: '0 0 12px', color: 'var(--text-primary)' }}>任务编排</h3>
            <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
              <input
                type="text"
                value={orchestrateInput}
                onChange={e => setOrchestrateInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleOrchestrate()}
                placeholder="输入任务描述..."
                style={{
                  flex: 1,
                  padding: '10px 14px',
                  borderRadius: '8px',
                  border: '1px solid var(--glass-border)',
                  background: 'var(--bg-secondary)',
                  color: 'var(--text-primary)',
                  fontSize: '14px',
                }}
              />
              <button
                onClick={handleOrchestrate}
                disabled={loading || !orchestrateInput.trim()}
                style={{
                  padding: '10px 20px',
                  borderRadius: '8px',
                  border: 'none',
                  background: loading ? '#6b7280' : 'var(--color-primary-1)',
                  color: 'white',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  fontSize: '14px',
                }}
              >
                {loading ? '执行中...' : '执行'}
              </button>
            </div>
            {orchestrateResult && (
              <pre style={{
                padding: '12px',
                borderRadius: '8px',
                background: orchestrateResult.error ? '#7f1d1d' : 'var(--bg-secondary)',
                fontSize: '13px',
                overflow: 'auto',
                color: orchestrateResult.error ? '#fca5a5' : 'var(--text-primary)',
              }}>
                {JSON.stringify(orchestrateResult, null, 2)}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
