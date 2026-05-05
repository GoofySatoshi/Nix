import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useChatContext } from '../context/ChatContext';
import { chatApi, environmentApi, messageApi } from '../services/api';

const SpinnerIcon: React.FC<{ size?: number }> = ({ size = 16 }) => (
  <svg className="spinner-icon" viewBox="0 0 24 24" width={size} height={size} fill="none">
    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="32" strokeLinecap="round" opacity="0.3" />
    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="32" strokeDashoffset="48" strokeLinecap="round" />
  </svg>
);

interface ChatConfig {
  id: number;
  name: string;
  vendor: string;
  model_name: string;
  model_list?: string[];
  is_default: boolean;
}

interface ToolCallInfo {
  tool_name: string;
  parameters: Record<string, any>;
  result: string;
  success: boolean;
}

interface Message {
  id?: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  tool_calls?: ToolCallInfo[];
  intent?: string;
  task_id?: number;
  plan_steps?: Array<{
    id: number;
    order: number;
    name: string;
    description: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
  }>;
  acceptance_results?: Array<{
    round: number;
    passed: boolean;
    results: Array<{id: number; status: string; reason: string; fix_instruction?: string}>;
  }>;
}

const VENDOR_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  azure: 'Azure',
  xiaomi: '小米',
  custom: '自定义',
};

const TOOL_DISPLAY_MAP: Record<string, string> = {
  'file_search': '🔍 搜索文件',
  'file_read': '📄 查看文件',
  'file_create': '📝 创建文件',
  'file_update': '✏️ 修改文件',
  'file_delete': '🗑️ 删除文件',
  'terminal_execute': '💻 执行命令',
  'file_find': '📂 查找文件',
};

const getToolDisplayName = (toolName: string): string => {
  return TOOL_DISPLAY_MAP[toolName] || toolName;
};

const getStepDisplayText = (step: any): string => {
  if (step.description) return step.description;
  if (step.display_name) return step.display_name;
  const mapped = TOOL_DISPLAY_MAP[step.tool_name || ''];
  if (mapped) return mapped;
  return step.tool_name || '';
};

const getToolCallParamSummary = (toolName: string, params: Record<string, any>): string => {
  if (toolName === 'file_read' && params.file_path) {
    return `查看文件: ${params.file_path}`;
  }
  if (toolName === 'terminal_execute' && params.command) {
    return `执行命令: ${params.command}`;
  }
  if (toolName === 'file_create' && params.file_path) {
    return `创建文件: ${params.file_path}`;
  }
  if (toolName === 'file_update' && params.file_path) {
    return `修改文件: ${params.file_path}`;
  }
  if (toolName === 'file_delete' && params.file_path) {
    return `删除文件: ${params.file_path}`;
  }
  if (toolName === 'file_search' && params.query) {
    return `搜索: ${params.query}`;
  }
  if (toolName === 'file_find' && params.pattern) {
    return `查找: ${params.pattern}`;
  }
  return '';
};

const getStreamKey = (agentId: number | null) => `nix_chat_stream_${agentId || 'default'}`;

const isImageUrl = (str: string): boolean =>
  /^https?:\/\//.test(str) || str.startsWith('/') || str.startsWith('data:');

const INTENT_DISPLAY_MAP: Record<string, string> = {
  'general_chat': '💬 日常对话',
  'file_operation': '📁 文件操作',
  'code_review': '🔍 代码审查',
  'code_generation': '✨ 代码生成',
  'terminal_command': '💻 终端命令',
  'project_analysis': '📊 项目分析',
  'information_query': '📖 信息查询',
};

const getIntentLabel = (intent: string): string => {
  return INTENT_DISPLAY_MAP[intent] || intent;
};

const ChatPanel: React.FC = () => {
  const {
    messages, setMessages,
    selectedAgentId, setSelectedAgentId,
    agents,
    user,
    selectedConfigId, setSelectedConfigId,
    selectedModel, setSelectedModel,
    messagesLoading,
    agentsLoading,
    agentsError,
  } = useChatContext();

  const [configs, setConfigs] = useState<ChatConfig[]>([]);
  const [agentDropdownOpen, setAgentDropdownOpen] = useState(false);
  const [input, setInput] = useState('');
  const getInitialStreamState = (agentId: number | null) => {
    try {
      const saved = localStorage.getItem(getStreamKey(agentId));
      return saved ? JSON.parse(saved) : null;
    } catch { return null; }
  };

  const initialStreamState = getInitialStreamState(selectedAgentId || null);

  const [loading, setLoading] = useState<boolean>(initialStreamState?.loading === true);
  const [error, setError] = useState<string | null>(null);
  const [streamingSteps, setStreamingSteps] = useState<Array<{
    type: string;
    message: string;
    tool_name?: string;
    display_name?: string;
    description?: string;
    parameters?: any;
    result?: string;
    success?: boolean;
    step?: number;
    timestamp: number;
  }>>(initialStreamState?.streamingSteps || []);
  const [showAllSteps, setShowAllSteps] = useState(false);
  const [streamingStatus, setStreamingStatus] = useState<string>(initialStreamState?.streamingStatus || '');
  const [currentTaskId, setCurrentTaskId] = useState<number | null>(initialStreamState?.currentTaskId || null);
  const [currentIntent, setCurrentIntent] = useState<string>(initialStreamState?.currentIntent || '');
  const [expandedToolCalls, setExpandedToolCalls] = useState<Record<number, boolean>>({});
  const [planSteps, setPlanSteps] = useState<Array<{
    id: number;
    order: number;
    name: string;
    description: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
  }>>([]);
  const [workingDirectory, setWorkingDirectory] = useState<string>('');
  const [envSummary, setEnvSummary] = useState<string>('');
  const [acceptanceCriteria, setAcceptanceCriteria] = useState<Array<{
    id: number;
    description: string;
    check_method: string;
  }>>([]);
  const [acceptanceTaskId, setAcceptanceTaskId] = useState<number | null>(null);
  const [acceptanceResults, setAcceptanceResults] = useState<Array<{
    round: number;
    passed: boolean;
    results: Array<{id: number; status: string; reason: string; fix_instruction?: string}>;
  }>>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isSubmittingRef = useRef(false);
  const replyReceivedRef = useRef(false);
  const agentSelectorRef = useRef<HTMLDivElement>(null);
  const isConfirmingRef = useRef(false);

  // 点击外部关闭智能体下拉菜单
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (agentSelectorRef.current && !agentSelectorRef.current.contains(e.target as Node)) {
        setAgentDropdownOpen(false);
      }
    };
    if (agentDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [agentDropdownOpen]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadConfigs(); }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingSteps]);

  useEffect(() => {
    const state = { loading, streamingSteps, streamingStatus, currentTaskId, currentIntent };
    localStorage.setItem(getStreamKey(selectedAgentId), JSON.stringify(state));
  }, [loading, streamingSteps, streamingStatus, currentTaskId, currentIntent, selectedAgentId]);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(getStreamKey(selectedAgentId));
      if (saved) {
        const state = JSON.parse(saved);
        setLoading(state.loading === true);
        setStreamingSteps(state.streamingSteps || []);
        setStreamingStatus(state.streamingStatus || '');
        setCurrentTaskId(state.currentTaskId || null);
        setCurrentIntent(state.currentIntent || '');
      } else {
        setLoading(false);
        setStreamingSteps([]);
        setStreamingStatus('');
        setCurrentTaskId(null);
        setCurrentIntent('');
      }
      setPlanSteps([]);
      setAcceptanceCriteria([]);
      setAcceptanceTaskId(null);
      setAcceptanceResults([]);
    } catch {
      setLoading(false);
      setStreamingSteps([]);
      setStreamingStatus('');
      setCurrentTaskId(null);
      setCurrentIntent('');
      setPlanSteps([]);
      setAcceptanceCriteria([]);
      setAcceptanceTaskId(null);
      setAcceptanceResults([]);
    }
  }, [selectedAgentId]);

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

  const startStream = async (apiMessages: Array<{ role: 'user' | 'assistant' | 'system'; content: string }>) => {
    replyReceivedRef.current = false;
    setLoading(true);
    setStreamingSteps([]);
    setPlanSteps([]);
    setStreamingStatus('正在连接 AI...');
    abortControllerRef.current = new AbortController();
    setCurrentTaskId(null);
    setCurrentIntent('');
    setError(null);

    try {
      const response = await chatApi.streamMessage(
        selectedConfigId || null, apiMessages, selectedModel,
        selectedAgentId || undefined,
        abortControllerRef.current?.signal
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No reader');

      const decoder = new TextDecoder();
      let buffer = '';

      // SSE 事件处理函数
      const processSSEEvent = (event: any) => {
        console.log('[SSE] event:', event.type);
        switch (event.type) {
          case 'status':
            setStreamingStatus(event.message);
            break;

          case 'intent':
            setCurrentIntent(event.intent);
            const intentDisplay = event.display_name || getIntentLabel(event.intent);
            setStreamingSteps(prev => [...prev, {
              type: 'intent',
              message: `意图识别: ${intentDisplay}`,
              timestamp: Date.now(),
            }]);
            break;

          case 'task_created':
            setCurrentTaskId(event.task_id);
            setStreamingSteps(prev => [...prev, {
              type: 'task_created',
              message: `任务 #${event.task_id} 已创建`,
              timestamp: Date.now(),
            }]);
            break;

          case 'tool_start':
            setStreamingStatus(`正在执行: ${getToolDisplayName(event.tool_name)}...`);
            setStreamingSteps(prev => [...prev, {
              type: 'tool_start',
              message: event.message,
              tool_name: event.tool_name,
              display_name: event.display_name,
              description: event.description,
              parameters: event.parameters,
              step: event.step,
              timestamp: Date.now(),
            }]);
            break;

          case 'tool_end':
            setStreamingSteps(prev => [...prev, {
              type: 'tool_end',
              message: event.message,
              tool_name: event.tool_name,
              display_name: event.display_name,
              description: event.description,
              parameters: event.parameters,
              result: event.result,
              success: event.success,
              step: event.step,
              timestamp: Date.now(),
            }]);
            break;

          case 'plan_generated':
            console.log('[SSE] plan_generated:', event);
            setPlanSteps((event.steps || []).map((s: any) => ({
              id: s.id,
              order: s.order,
              name: s.name,
              description: s.description,
              status: s.status || 'pending',
            })));
            break;

          case 'step_completed':
            setPlanSteps(prev => prev.map(step =>
              step.order === event.step_order
                ? { ...step, status: event.status }
                : step.order === event.step_order + 1
                  ? { ...step, status: 'running' }
                  : step
            ));
            break;

          case 'acceptance_criteria_generated':
            console.log('[SSE] acceptance_criteria_generated:', event);
            setAcceptanceCriteria(event.criteria || []);
            setAcceptanceTaskId(event.task_id);
            break;

          case 'acceptance_result':
            setAcceptanceResults(prev => [...prev, {
              round: event.round,
              passed: event.passed,
              results: event.results || []
            }]);
            break;

          case 'reply':
            console.log('[SSE] reply event:', event);
            replyReceivedRef.current = true;
            // 防御性清理：移除可能泄露的工具调用标记
            let cleanedReply = event.reply || event.content || '';
            cleanedReply = cleanedReply
              .replace(/<function_calls>[\s\S]*?<\/function_calls>/g, '')
              .replace(/<function_calls>[\s\S]*/g, '')
              .replace(/<invoke[\s\S]*?<\/invoke>/g, '')
              .replace(/<parameter[\s\S]*?<\/parameter>/g, '')
              .replace(/<｜DSML｜[^>]*>[\s\S]*/g, '')
              .replace(/<tool_call>[\s\S]*?<\/tool_call>/g, '')
              .replace(/<tool_call>[\s\S]*/g, '')
              .replace(/<function=[^>]*>[\s\S]*?<\/function>/g, '')
              .replace(/<function=[^>]*>[\s\S]*/g, '')
              .replace(/<parameter=[^>]*>[\s\S]*?<\/parameter>/g, '')
              .replace(/<\|(?:plugin|interpreter|action|tool_call|function_call)\|>[\s\S]*/g, '')
              .trim();
            if (!cleanedReply) {
              cleanedReply = '任务已完成。';
            }
            setMessages(prev => [...prev, {
              role: 'assistant',
              content: cleanedReply,
              tool_calls: event.tool_calls,
              intent: event.intent,
              task_id: event.task_id,
              plan_steps: planSteps.length > 0 ? [...planSteps] : undefined,
              acceptance_results: acceptanceResults.length > 0 ? [...acceptanceResults] : undefined,
            }]);
            setPlanSteps([]);
            setAcceptanceResults([]);

            setLoading(false);
            setStreamingSteps([]);
            setStreamingStatus('');
            setCurrentTaskId(null);
            setCurrentIntent('');
            localStorage.removeItem(getStreamKey(selectedAgentId));
            abortControllerRef.current = null;
            break;

          case 'error':
            setMessages(prev => [...prev, {
              role: 'assistant',
              content: `❌ ${event.message}`,
            }]);

            setLoading(false);
            setStreamingSteps([]);
            setPlanSteps([]);
            setStreamingStatus('');
            setCurrentTaskId(null);
            setCurrentIntent('');
            setAcceptanceResults([]);
            localStorage.removeItem(getStreamKey(selectedAgentId));
            abortControllerRef.current = null;
            break;
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          // 处理 buffer 中剩余未处理的数据
          const remaining = buffer + decoder.decode();
          if (remaining.trim()) {
            const remainingLines = remaining.split('\n');
            for (const line of remainingLines) {
              if (line.startsWith('data: ')) {
                try {
                  const event = JSON.parse(line.slice(6));
                  console.log('[SSE] Final buffer event:', event.type, event);
                  processSSEEvent(event);
                } catch (e) { /* ignore */ }
              }
            }
          }
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.slice(6));
              processSSEEvent(event);
            } catch (e) {
              // JSON 解析失败，跳过
            }
          }
        }
      }

      // 流正常结束后，若未收到 reply 事件，确保 loading 被重置
      if (!replyReceivedRef.current) {
        console.warn('[SSE] Stream ended without reply event, resetting loading state');
        setLoading(false);
        setStreamingSteps([]);
        setStreamingStatus('');
        localStorage.removeItem(getStreamKey(selectedAgentId));
        abortControllerRef.current = null;
      }
    } catch (e: any) {
      // 用户主动中断，不需要 fallback
      if (e.name === 'AbortError' || abortControllerRef.current?.signal.aborted) {
        setLoading(false);
        setStreamingSteps([]);
        setPlanSteps([]);
        setStreamingStatus('');
        setCurrentTaskId(null);
        setCurrentIntent('');
        setAcceptanceResults([]);
        localStorage.removeItem(getStreamKey(selectedAgentId));
        abortControllerRef.current = null;
        return;
      }
      // 若 SSE 已返回 reply，避免 fallback 导致重复回答
      if (replyReceivedRef.current) {
        setLoading(false);
        setStreamingSteps([]);
        setPlanSteps([]);
        setStreamingStatus('');
        setCurrentTaskId(null);
        setCurrentIntent('');
        setAcceptanceResults([]);
        localStorage.removeItem(getStreamKey(selectedAgentId));
        abortControllerRef.current = null;
        return;
      }
      try {
        const res = await chatApi.sendMessage(
          selectedConfigId, apiMessages, selectedModel, selectedAgentId || undefined
        );
        const assistantMsg = {
          role: 'assistant' as const,
          content: res.reply,
          tool_calls: (res as any).tool_calls || [],
          intent: (res as any).intent || '',
          task_id: (res as any).task_id || undefined,
        };
        setMessages(prev => [...prev, assistantMsg]);

      } catch (fallbackErr: any) {
        const errorMsg = `❌ 请求失败: ${fallbackErr.message}`;
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: errorMsg,
        }]);

      }
      setLoading(false);
      setStreamingSteps([]);
      setPlanSteps([]);
      setStreamingStatus('');
      setCurrentTaskId(null);
      setCurrentIntent('');
      setAcceptanceResults([]);
      localStorage.removeItem(getStreamKey(selectedAgentId));
      abortControllerRef.current = null;
    }
  };

  const handleSend = async () => {
    if (isSubmittingRef.current || loading || !input.trim()) return;
    isSubmittingRef.current = true;
    replyReceivedRef.current = false;
    try {

    const userMessage: Message = { role: 'user', content: input.trim() };
    const updated = [...messages, userMessage];
    setMessages(updated);
    setInput('');
    setError(null);

    setAcceptanceCriteria([]);
    setAcceptanceTaskId(null);
    setAcceptanceResults([]);

    const systemContent = [
      `用户的工作目录为: ${workingDirectory}，所有文件操作限制在此目录内。`,
      envSummary ? `\n用户设备环境信息:\n${envSummary}\n请根据以上环境信息生成兼容的终端命令。` : ''
    ].join('');

    const apiMessages: Array<{ role: 'user' | 'assistant' | 'system'; content: string }> = [
      { role: 'system' as const, content: systemContent },
      ...updated.filter(m => m.role !== 'system').map(m => ({ role: m.role, content: m.content }))
    ];

    await startStream(apiMessages);
    } finally {
      isSubmittingRef.current = false;
    }
  };

  const handleConfirmCriteria = async () => {
    if (!acceptanceTaskId || isConfirmingRef.current || loading) return;
    isConfirmingRef.current = true;
    try {
      const token = localStorage.getItem('nix_token');
      await fetch('http://localhost:8000/api/chat/confirm-criteria', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          task_id: acceptanceTaskId,
          criteria: acceptanceCriteria
        })
      });
      setAcceptanceCriteria([]);
      setAcceptanceResults([]);

      const systemContent = [
        `confirmed_task_id: ${acceptanceTaskId}`,
        `用户的工作目录为: ${workingDirectory}，所有文件操作限制在此目录内。`,
        envSummary ? `\n用户设备环境信息:\n${envSummary}\n请根据以上环境信息生成兼容的终端命令。` : ''
      ].join('');

      const apiMessages: Array<{ role: 'user' | 'assistant' | 'system'; content: string }> = [
        { role: 'system' as const, content: systemContent },
        { role: 'user' as const, content: '请开始执行任务' }
      ];
      await startStream(apiMessages);
    } catch (err) {
      console.error('确认验收标准失败:', err);
      setError('确认验收标准失败');
    } finally {
      isConfirmingRef.current = false;
    }
  };

  const handleAbort = async () => {
    const confirmed = window.confirm(
      '确定要打断当前 AI 任务吗？\n\n打断后 AI 将停止当前操作，已完成的步骤不会丢失。'
    );
    if (!confirmed) return;

    // 1. 中止 SSE 连接
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // 2. 调用后端打断 API
    if (currentTaskId) {
      try {
        await chatApi.abortTask(currentTaskId);
      } catch (e) {
        console.warn('打断请求失败:', e);
      }
    }

    // 3. 更新 UI 状态
    setLoading(false);
    setStreamingStatus('任务已被打断');

    // 4. 添加一条系统消息
    setMessages(prev => [...prev, {
      role: 'assistant' as const,
      content: '⏹ 任务已被用户打断。',
    }]);

    // 6. 清理流式状态
    setStreamingSteps([]);
    setPlanSteps([]);
    setCurrentTaskId(null);
    setCurrentIntent('');
    setAcceptanceCriteria([]);
    setAcceptanceTaskId(null);
    setAcceptanceResults([]);
    localStorage.removeItem(getStreamKey(selectedAgentId));
    abortControllerRef.current = null;
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !loading && !isSubmittingRef.current) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClearChat = async () => {
    if (!window.confirm('确定要清除当前对话的所有历史消息吗？此操作不可恢复。')) {
      return;
    }
    setMessages([]);
    setStreamingSteps([]);
    setStreamingStatus('');
    setCurrentTaskId(null);
    setCurrentIntent('');
    setLoading(false);
    setExpandedToolCalls({});
    setShowAllSteps(false);
    setPlanSteps([]);
    setAcceptanceCriteria([]);
    setAcceptanceTaskId(null);
    setAcceptanceResults([]);
    // 调用数据库 API 清除消息（静默失败）
    if (selectedAgentId !== null) {
      try {
        await messageApi.clearMessages(selectedAgentId);
      } catch (e) {
        console.error('清除消息失败:', e);
      }
    }
    localStorage.removeItem(getStreamKey(selectedAgentId));
  };

  const selectedAgent = agents.find(a => a.id === selectedAgentId);
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
        <div className="chat-agent-selector" ref={agentSelectorRef} style={{ position: 'relative' }}>
          <div
            className="agent-select-trigger"
            onClick={() => !agentsLoading && setAgentDropdownOpen(!agentDropdownOpen)}
            title={agentsError ? `⚠️ ${agentsError}` : '选择智能体'}
            style={agentsError ? { borderColor: 'rgba(239, 68, 68, 0.5)' } : undefined}
          >
            {(() => {
              const sel = agents.find(a => a.id === selectedAgentId);
              if (agentsLoading) return <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><SpinnerIcon size={14} /> 加载中...</span>;
              if (agentsError) return <span>⚠️ 加载失败</span>;
              if (!sel) return <span>🤖 默认助手</span>;
              return (
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  {sel.avatar && isImageUrl(sel.avatar) ? (
                    <img src={sel.avatar} alt="" style={{ width: 20, height: 20, borderRadius: '50%', objectFit: 'cover' }} />
                  ) : (
                    <span>{sel.avatar && sel.avatar.length <= 4 ? sel.avatar : '🤖'}</span>
                  )}
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{sel.name}</span>
                </span>
              );
            })()}
            <span style={{ marginLeft: 'auto', fontSize: '10px', opacity: 0.6 }}>▼</span>
          </div>
          {agentDropdownOpen && (
            <div className="agent-dropdown-menu">
              <div
                className={`agent-dropdown-item ${!selectedAgentId ? 'active' : ''}`}
                onClick={() => { setSelectedAgentId(null); setAgentDropdownOpen(false); }}
              >
                <span style={{ width: 20, textAlign: 'center' }}>🤖</span>
                <span>默认助手</span>
              </div>
              {agents.map(a => (
                <div
                  key={a.id}
                  className={`agent-dropdown-item ${selectedAgentId === a.id ? 'active' : ''}`}
                  onClick={() => { setSelectedAgentId(a.id); setAgentDropdownOpen(false); }}
                >
                  {a.avatar && isImageUrl(a.avatar) ? (
                    <img src={a.avatar} alt="" style={{ width: 20, height: 20, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }} />
                  ) : (
                    <span style={{ width: 20, textAlign: 'center', flexShrink: 0 }}>{a.avatar && a.avatar.length <= 4 ? a.avatar : '🤖'}</span>
                  )}
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.name}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        {selectedConfig && (
          <span className="chat-model-badge">
            {VENDOR_LABELS[selectedConfig.vendor] || selectedConfig.vendor}
          </span>
        )}
        <button
          className="btn"
          onClick={handleClearChat}
          title="清除对话"
          style={{
            marginLeft: 'auto',
            fontSize: '12px',
            padding: '4px 10px',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            background: 'var(--glass-bg)',
            border: '1px solid var(--glass-border)',
            borderRadius: 'var(--radius-btn)',
            backdropFilter: 'blur(8px)',
            flexShrink: 0,
          }}
        >
          🗑️ 清除对话
        </button>
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
          flexShrink: 1,
          minWidth: 0,
          overflow: 'hidden',
          maxWidth: '100%',
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          <span style={{
            fontFamily: "'SF Mono', monospace",
            color: 'var(--color-primary-2)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            minWidth: 0,
          }}>
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
            {messagesLoading && messages.length === 0 && (
              <div className="chat-empty">
                <p>正在加载历史消息...</p>
              </div>
            )}
            {!messagesLoading && messages.length === 0 && (
              <div className="chat-empty">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.3">
                  <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
                </svg>
                <p>开始与 AI 对话</p>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>在下方输入消息，选择上方模型开始对话</p>
              </div>
            )}
            {messages.map((m, idx) => (
              <div key={m.id ?? idx} className={`chat-message chat-message-${m.role}`}>
                <div className="chat-message-avatar">
                  {m.role === 'user' ? (
                    user?.avatar ? (
                      <img src={user.avatar} alt="用户头像" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    ) : (
                      <span>👤</span>
                    )
                  ) : (
                    selectedAgent?.avatar ? (
                      isImageUrl(selectedAgent.avatar) ? (
                        <img src={selectedAgent.avatar} alt="AI头像" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      ) : (
                        <span>{selectedAgent.avatar}</span>
                      )
                    ) : (
                      <span>🤖</span>
                    )
                  )}
                </div>
                <div className={`chat-message-bubble ${m.role === 'assistant' ? 'markdown-view' : ''}`}>
                  {m.role === 'assistant' && (m.intent || m.task_id) && (
                    <div className="chat-message-meta">
                      {m.intent && m.intent !== 'general_chat' && (
                        <span className={`intent-badge intent-${m.intent}`}>
                          {getIntentLabel(m.intent)}
                        </span>
                      )}
                      {m.task_id && (
                        <span className="task-link" onClick={() => window.location.href = '/tasks'}>
                          📋 任务 #{m.task_id}
                        </span>
                      )}
                    </div>
                  )}
                  {m.role === 'assistant' && m.tool_calls && m.tool_calls.length > 0 && (
                    <div className="tool-calls-section">
                      <div
                        className="tool-calls-header"
                        onClick={() => setExpandedToolCalls(prev => ({ ...prev, [idx]: prev[idx] === false ? true : false }))}
                      >
                        <span>🔧 工具调用 ({m.tool_calls.length})</span>
                        <span className="tool-calls-toggle">{expandedToolCalls[idx] !== false ? '▼' : '▶'}</span>
                      </div>
                      {expandedToolCalls[idx] !== false && (
                        <div className="tool-calls-list">
                          {m.tool_calls.map((tc, j) => {
                            const paramSummary = getToolCallParamSummary(tc.tool_name, tc.parameters);
                            const resultText = tc.result || '';
                            const resultExpanded = resultText.length <= 200;
                            return (
                              <div key={j} className={`tool-call-item ${tc.success ? 'success' : 'error'}`}>
                                <div className="tool-call-name">
                                  <span className={`tool-call-status ${tc.success ? 'success' : 'error'}`}>
                                    {tc.success ? '✓' : '✗'}
                                  </span>
                                  {getToolDisplayName(tc.tool_name)}
                                </div>
                                {paramSummary && (
                                  <div className="tool-call-param-summary">{paramSummary}</div>
                                )}
                                {!paramSummary && (
                                  <div className="tool-call-params">
                                    <details>
                                      <summary>参数</summary>
                                      <pre>{JSON.stringify(tc.parameters, null, 2)}</pre>
                                    </details>
                                  </div>
                                )}
                                <div className="tool-call-result">
                                  {resultExpanded ? (
                                    <pre>{resultText}</pre>
                                  ) : (
                                    <details>
                                      <summary>结果</summary>
                                      <pre>{resultText.slice(0, 100) + '...'}</pre>
                                    </details>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}
                  {m.plan_steps && m.plan_steps.length > 0 && (
                    <div className="task-checklist task-checklist-history">
                      <div className="checklist-header">
                        <span className="checklist-title">📋 执行计划</span>
                        <span className="checklist-progress">
                          {m.plan_steps.filter((s: any) => s.status === 'completed').length}/{m.plan_steps.length}
                        </span>
                      </div>
                      <div className="checklist-items">
                        {m.plan_steps.map((step: any, stepIdx: number) => (
                          <div key={step.id} className={`checklist-item checklist-${step.status}`}>
                            <span className="checklist-order">{stepIdx + 1}</span>
                            <span className="checklist-status-icon">
                              {step.status === 'completed' ? '✅' :
                               step.status === 'running' ? <SpinnerIcon size={16} /> :
                               step.status === 'failed' ? '❌' : '📋'}
                            </span>
                            <div className="checklist-content">
                              <span className="checklist-name">{step.name}</span>
                              {step.description && (
                                <span className="checklist-desc">{step.description}</span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {m.acceptance_results && m.acceptance_results.length > 0 && (
                    <div className="acceptance-results">
                      {m.acceptance_results.map((result, idx) => (
                        <div key={idx} className={`acceptance-report ${result.passed ? 'passed' : 'failed'}`}>
                          <div className="report-header">
                            <span className="report-title">验收报告（第{result.round}轮）</span>
                            <span className={`report-status ${result.passed ? 'status-passed' : 'status-failed'}`}>
                              {result.passed ? '✅ 通过' : '❌ 未通过'}
                            </span>
                          </div>
                          <div className="report-items">
                            {result.results.map((item) => (
                              <div key={item.id} className={`report-item ${item.status}`}>
                                <span className="item-icon">{item.status === 'passed' ? '✅' : '❌'}</span>
                                <div className="item-content">
                                  <span className="item-reason">{item.reason}</span>
                                  {item.fix_instruction && (
                                    <span className="item-fix">修复: {item.fix_instruction}</span>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {m.role === 'assistant' ? (
                    <ReactMarkdown
                      components={{
                        code({ node, inline, className, children, ...props }: any) {
                          const match = /language-(\w+)/.exec(className || '');
                          return !inline && match ? (
                            <SyntaxHighlighter
                              style={oneDark}
                              language={match[1]}
                              PreTag="div"
                              customStyle={{
                                margin: '8px 0',
                                borderRadius: '8px',
                                fontSize: '0.85rem',
                              }}
                              {...props}
                            >
                              {String(children).replace(/\n$/, '')}
                            </SyntaxHighlighter>
                          ) : (
                            <code className="inline-code" {...props}>
                              {children}
                            </code>
                          );
                        },
                      }}
                    >
                      {m.content}
                    </ReactMarkdown>
                  ) : (
                    m.content
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="chat-message chat-message-assistant">
                <div className="chat-message-avatar">
                  {selectedAgent?.avatar ? (
                    isImageUrl(selectedAgent.avatar) ? (
                      <img src={selectedAgent.avatar} alt="AI头像" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    ) : (
                      <span>{selectedAgent.avatar}</span>
                    )
                  ) : (
                    <span>🤖</span>
                  )}
                </div>
                <div className="chat-message-bubble">
                  <div className="ai-streaming-status">
                    <div className="thinking-dots">
                      <span></span><span></span><span></span>
                    </div>
                    <span className="thinking-text">{streamingStatus || 'AI 正在处理...'}</span>
                  </div>
                  {(currentIntent || currentTaskId) && (
                    <div className="chat-message-meta" style={{ marginTop: '8px' }}>
                      {currentIntent && currentIntent !== 'general_chat' && (
                        <span className={`intent-badge intent-${currentIntent}`}>
                          {getIntentLabel(currentIntent)}
                        </span>
                      )}
                      {currentTaskId && (
                        <span className="task-link">📋 任务 #{currentTaskId}</span>
                      )}
                    </div>
                  )}
                  {planSteps.length > 0 && (
                    <div className="task-checklist">
                      <div className="checklist-header">
                        <span className="checklist-title">📋 执行计划</span>
                        <span className="checklist-progress">
                          {planSteps.filter(s => s.status === 'completed').length}/{planSteps.length}
                        </span>
                      </div>
                      <div className="checklist-items">
                        {planSteps.map((step, stepIdx) => (
                          <div key={step.id} className={`checklist-item checklist-${step.status}`}>
                            <span className="checklist-order">{stepIdx + 1}</span>
                            <span className="checklist-status-icon">
                              {step.status === 'completed' ? '✅' :
                               step.status === 'running' ? <SpinnerIcon size={16} /> :
                               step.status === 'failed' ? '❌' : '📋'}
                            </span>
                            <div className="checklist-content">
                              <span className="checklist-name">{step.name}</span>
                              {step.description && (
                                <span className="checklist-desc">{step.description}</span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {streamingSteps.length > 0 && (
                    <div className="streaming-steps">
                      {streamingSteps.length > 6 && !showAllSteps && (
                        <div
                          className="streaming-steps-expand"
                          onClick={() => setShowAllSteps(true)}
                        >
                          <span>查看更早 {streamingSteps.length - 6} 条记录 ▼</span>
                        </div>
                      )}
                      {(showAllSteps ? streamingSteps : streamingSteps.slice(-6)).map((step, idx, arr) => (
                        <div key={idx} className={`streaming-step streaming-step-${step.type}`}>
                          {step.type === 'tool_start' && (
                            <span className="step-content">
                              <span className="step-icon"><SpinnerIcon size={14} /></span>
                              <span className="step-text">{getStepDisplayText(step)}</span>
                              <span className="step-badge">执行中</span>
                            </span>
                          )}
                          {step.type === 'tool_end' && (
                            <span className="step-content">
                              <span className="step-icon">{step.success ? '✅' : '❌'}</span>
                              <span className="step-text">{getStepDisplayText(step)}</span>
                              <span className={`step-badge ${step.success ? 'success' : 'error'}`}>
                                {step.success ? '完成' : '失败'}
                              </span>
                              {step.result && (
                                <details className="step-details">
                                  <summary>查看结果</summary>
                                  <pre>{typeof step.result === 'string' && step.result.length > 300
                                    ? step.result.slice(0, 300) + '...'
                                    : step.result}</pre>
                                </details>
                              )}
                            </span>
                          )}
                          {step.type === 'intent' && (
                            <span className="step-content">
                              <span className="step-icon">🎯</span>
                              <span className="step-text">{step.message}</span>
                            </span>
                          )}
                          {step.type === 'task_created' && (
                            <span className="step-content">
                              <span className="step-icon">📋</span>
                              <span className="step-text">{step.message}</span>
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                  {acceptanceResults.length > 0 && (
                    <div className="acceptance-results">
                      {acceptanceResults.map((result, idx) => (
                        <div key={idx} className={`acceptance-report ${result.passed ? 'passed' : 'failed'}`}>
                          <div className="report-header">
                            <span className="report-title">验收报告（第{result.round}轮）</span>
                            <span className={`report-status ${result.passed ? 'status-passed' : 'status-failed'}`}>
                              {result.passed ? '✅ 通过' : '❌ 未通过'}
                            </span>
                          </div>
                          <div className="report-items">
                            {result.results.map((item) => (
                              <div key={item.id} className={`report-item ${item.status}`}>
                                <span className="item-icon">{item.status === 'passed' ? '✅' : '❌'}</span>
                                <div className="item-content">
                                  <span className="item-reason">{item.reason}</span>
                                  {item.fix_instruction && (
                                    <span className="item-fix">修复: {item.fix_instruction}</span>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
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

          {/* 验收标准确认 */}
          {(() => { console.log('[Render] acceptanceCriteria:', acceptanceCriteria.length, 'loading:', loading); return null; })()}
          {acceptanceCriteria.length > 0 && !loading && (
            <div className="acceptance-criteria-panel">
              <div className="acceptance-header">
                <span className="acceptance-title">📋 验收标准确认</span>
                <span className="acceptance-subtitle">请确认或编辑以下验收标准，确认后开始执行任务</span>
              </div>
              <div className="acceptance-list">
                {acceptanceCriteria.map((item, idx) => (
                  <div key={item.id} className="acceptance-item">
                    <span className="acceptance-id">{idx + 1}.</span>
                    <input
                      className="acceptance-input"
                      value={item.description}
                      onChange={(e) => {
                        setAcceptanceCriteria(prev => prev.map((c, i) => 
                          i === idx ? {...c, description: e.target.value} : c
                        ));
                      }}
                    />
                    <button className="acceptance-remove-btn" onClick={() => {
                      setAcceptanceCriteria(prev => prev.filter((_, i) => i !== idx));
                    }}>✕</button>
                  </div>
                ))}
              </div>
              <div className="acceptance-actions">
                <button className="acceptance-add-btn" onClick={() => {
                  setAcceptanceCriteria(prev => [...prev, {
                    id: prev.length + 1,
                    description: '',
                    check_method: '人工确认'
                  }]);
                }}>+ 添加标准</button>
                <button className="acceptance-confirm-btn" onClick={handleConfirmCriteria}>
                  确认并执行
                </button>
              </div>
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
              className={`btn ${loading ? 'btn-abort' : 'btn-primary'} chat-send-btn`}
              onClick={loading ? handleAbort : handleSend}
              disabled={!loading && !input.trim()}
            >
              {loading ? '⏹ 打断' : '发送'}
            </button>
          </div>
    </div>
  );
};

export default ChatPanel;
