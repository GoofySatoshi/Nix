// API 配置常量
// 使用相对路径，通过 nginx 反代访问后端
export const API_BASE_URL = '';

// 认证 token 存储 key
export const AUTH_TOKEN_KEY = 'auth_token';

export const API_ENDPOINTS = {
  // 认证相关接口
  AUTH_REGISTER: '/api/auth/register',
  AUTH_LOGIN: '/api/auth/login',

  // 智能体相关接口
  AGENTS: '/api/agents',
  AGENT_TYPES: '/api/agents/types',
  START_AGENT: (id: number) => `/api/agents/${id}/start`,
  STOP_AGENT: (id: number) => `/api/agents/${id}/stop`,
  
  // 设置相关接口
  SETTINGS: '/api/settings',

  // 对话相关接口
  CHAT: '/api/chat',
  CHAT_CONFIGS: '/api/chat/configs',
};
