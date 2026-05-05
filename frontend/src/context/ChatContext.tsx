import React, { createContext, useContext, useState, useEffect } from 'react';
import { authApi, agentApi, messageApi, taskApi } from '../services/api';

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

interface UserProfile {
  id: number;
  username: string;
  email: string;
  avatar?: string;
}

interface ChatContextType {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  selectedAgentId: number | null;
  setSelectedAgentId: React.Dispatch<React.SetStateAction<number | null>>;
  agents: any[];
  setAgents: React.Dispatch<React.SetStateAction<any[]>>;
  agentsLoading: boolean;
  setAgentsLoading: React.Dispatch<React.SetStateAction<boolean>>;
  agentsError: string | null;
  setAgentsError: React.Dispatch<React.SetStateAction<string | null>>;
  user: UserProfile | null;
  setUser: React.Dispatch<React.SetStateAction<UserProfile | null>>;
  selectedConfigId: number | null;
  setSelectedConfigId: React.Dispatch<React.SetStateAction<number | null>>;
  selectedModel: string;
  setSelectedModel: React.Dispatch<React.SetStateAction<string>>;
  messagesLoading: boolean;
  setMessagesLoading: React.Dispatch<React.SetStateAction<boolean>>;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export const ChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(() => {
    const saved = localStorage.getItem('nix_chat_agent_id');
    return saved ? Number(saved) : null;
  });
  const [agents, setAgents] = useState<any[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const [agentsError, setAgentsError] = useState<string | null>(null);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [selectedConfigId, setSelectedConfigId] = useState<number | null>(() => {
    const saved = localStorage.getItem('nix_chat_config_id');
    return saved ? Number(saved) : null;
  });
  const [selectedModel, setSelectedModel] = useState<string>(() => {
    return localStorage.getItem('nix_chat_model') || '';
  });
  const [messagesLoading, setMessagesLoading] = useState(false);

  // 加载用户信息（仅执行一次）
  useEffect(() => {
    authApi.getProfile().then(data => setUser(data)).catch(() => {});
  }, []);

  // 加载智能体列表（仅执行一次）
  useEffect(() => {
    const loadAgents = async () => {
      setAgentsLoading(true);
      setAgentsError(null);
      try {
        const data = await agentApi.getAgents();
        if (!Array.isArray(data)) {
          setAgents([]);
          setAgentsError('智能体数据格式异常');
          return;
        }
        const validAgents = data.filter((a: any) => a?.id && a?.name);
        setAgents(validAgents);
        if (!selectedAgentId && validAgents.length > 0) {
          setSelectedAgentId(validAgents[0].id);
        }
      } catch (e: any) {
        console.error('加载智能体列表失败:', e);
        setAgentsError(e.message || '加载失败');
        setAgents([]);
      } finally {
        setAgentsLoading(false);
      }
    };
    loadAgents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 加载消息（当 selectedAgentId 变化时）
  useEffect(() => {
    const loadMessages = async () => {
      setMessagesLoading(true);
      try {
        const data = await messageApi.getMessages(selectedAgentId || undefined);
        // 对有 task_id 的 assistant 消息加载步骤
        const messagesWithSteps = await Promise.all(
          data.map(async (m: any) => {
            const baseMsg = {
              id: m.id,
              role: m.role,
              content: m.content,
              tool_calls: m.tool_calls,
              intent: m.intent,
              task_id: m.task_id,
            };
            if (m.role === 'assistant' && m.task_id) {
              try {
                const steps = await taskApi.getSteps(m.task_id);
                if (steps.length > 0) {
                  return { ...baseMsg, plan_steps: steps };
                }
              } catch {}
            }
            return baseMsg;
          })
        );
        setMessages(messagesWithSteps);
      } catch (e) {
        console.error('加载消息失败:', e);
        setMessages([]);
      } finally {
        setMessagesLoading(false);
      }
    };
    loadMessages();
  }, [selectedAgentId]);

  // localStorage 同步：selectedAgentId
  useEffect(() => {
    if (selectedAgentId !== null) {
      localStorage.setItem('nix_chat_agent_id', String(selectedAgentId));
    }
  }, [selectedAgentId]);

  // localStorage 同步：selectedConfigId
  useEffect(() => {
    if (selectedConfigId !== null) {
      localStorage.setItem('nix_chat_config_id', String(selectedConfigId));
    }
  }, [selectedConfigId]);

  // localStorage 同步：selectedModel
  useEffect(() => {
    if (selectedModel) {
      localStorage.setItem('nix_chat_model', selectedModel);
    }
  }, [selectedModel]);

  return (
    <ChatContext.Provider
      value={{
        messages, setMessages,
        selectedAgentId, setSelectedAgentId,
        agents, setAgents,
        agentsLoading, setAgentsLoading,
        agentsError, setAgentsError,
        user, setUser,
        selectedConfigId, setSelectedConfigId,
        selectedModel, setSelectedModel,
        messagesLoading, setMessagesLoading,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
};

export const useChatContext = (): ChatContextType => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChatContext must be used within a ChatProvider');
  }
  return context;
};
