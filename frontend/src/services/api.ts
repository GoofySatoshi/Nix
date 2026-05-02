import { API_BASE_URL, API_ENDPOINTS, AUTH_TOKEN_KEY } from '../constants/api';

// ============ Token 管理 ============

let authToken: string | null = localStorage.getItem(AUTH_TOKEN_KEY);

export function getAuthToken(): string | null {
  return authToken;
}

export function setAuthToken(token: string): void {
  authToken = token;
  localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function clearAuthToken(): void {
  authToken = null;
  localStorage.removeItem(AUTH_TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return authToken !== null && authToken.length > 0;
}

// ============ 通用请求函数 ============

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };

    // 自动附带 Authorization header
    if (authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      // token 过期或无效时清除
      if (response.status === 401) {
        clearAuthToken();
        throw new Error('登录已过期，请重新登录');
      }
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('API request failed:', error);
    throw error;
  }
}

// ============ 认证相关 API ============

export const authApi = {
  register: (data: { username: string; email: string; password: string }) =>
    request<any>(API_ENDPOINTS.AUTH_REGISTER, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  login: (data: { email: string; password: string }) =>
    request<{ access_token: string; token_type: string }>(API_ENDPOINTS.AUTH_LOGIN, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getProfile: () => request<any>('/api/auth/profile'),
  updateProfile: (data: any) => request<any>('/api/auth/profile', { method: 'PUT', body: JSON.stringify(data) }),
};

// ============ 智能体相关 API ============

export const agentApi = {
  getAgents: () => request<any[]>('/api/agents'),
  
  getAgentTypes: () => request<{ types: string[] }>('/api/agents/types'),
  
  createAgent: (agentData: any) => request<any>('/api/agents', {
    method: 'POST',
    body: JSON.stringify(agentData),
  }),
  
  updateAgent: (id: number, agentData: any) => request<any>(`/api/agents/${id}`, {
    method: 'PUT',
    body: JSON.stringify(agentData),
  }),
  
  startAgent: (id: number) => request<any>(`/api/agents/${id}/start`, {
    method: 'POST',
  }),
  
  stopAgent: (id: number) => request<any>(`/api/agents/${id}/stop`, {
    method: 'POST',
  }),

  getAgentModel: (id: number) => request<any>(`/api/agents/${id}/model`),

  dispatchTask: (agentId: number, data: { source_agent_id: number; target_agent_id: number; task_name: string; task_description: string; priority?: number; parameters?: Record<string, any> }) =>
    request<any>(`/api/agents/${agentId}/dispatch`, { method: 'POST', body: JSON.stringify(data) }),

  getAvailableAgents: () => request<any[]>('/api/agents/schedule/available'),

  autoSchedule: (data: { task_name: string; task_description: string; preferred_agent_type?: string; priority?: number }) =>
    request<any>('/api/agents/schedule/auto', { method: 'POST', body: JSON.stringify(data) }),
};

// ============ 任务相关 API ============

export const taskApi = {
  getTasks: (params?: { status?: string; agent_id?: number; search?: string }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set('status', params.status);
    if (params?.agent_id) query.set('agent_id', String(params.agent_id));
    if (params?.search) query.set('search', params.search);
    const qs = query.toString();
    return request<any[]>(`/api/tasks${qs ? '?' + qs : ''}`);
  },
  
  createTask: (taskData: any) => request<any>('/api/tasks', {
    method: 'POST',
    body: JSON.stringify(taskData),
  }),

  updateTask: (id: number, taskData: any) => request<any>(`/api/tasks/${id}`, {
    method: 'PUT',
    body: JSON.stringify(taskData),
  }),

  deleteTask: (id: number) => request<any>(`/api/tasks/${id}`, {
    method: 'DELETE',
  }),

  executeTask: (id: number) => request<any>(`/api/tasks/${id}/execute`, {
    method: 'POST',
  }),
};

// ============ 设置相关 API ============

interface ApiKeyConfig {
  name: string;
  vendor: string;
  model_name: string;
  model_list?: string[];
  api_key: string;
  api_base_url?: string;
  model_list_url?: string;
  is_default?: boolean;
}

interface FetchModelsResult {
  models: string[];
  raw_count: number;
  vendor: string;
}

export const settingsApi = {
  listConfigs: () => request<any[]>('/api/settings'),

  createConfig: (data: ApiKeyConfig) =>
    request<any>('/api/settings', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateConfig: (id: number, data: Partial<ApiKeyConfig>) =>
    request<any>(`/api/settings/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteConfig: (id: number) =>
    request<any>(`/api/settings/${id}`, {
      method: 'DELETE',
    }),

  fetchModels: (modelListUrl: string, apiKey: string, vendor: string): Promise<FetchModelsResult> =>
    request<FetchModelsResult>('/api/settings/fetch-models', {
      method: 'POST',
      body: JSON.stringify({ model_list_url: modelListUrl, api_key: apiKey, vendor }),
    }),
};

// ============ 对话相关 API ============

interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

interface ChatConfigItem {
  id: number;
  name: string;
  vendor: string;
  model_name: string;
  model_list?: string[];
  is_default: boolean;
}

interface ChatResponse {
  reply: string;
  model_name: string;
  vendor: string;
  config_name: string;
}

export const chatApi = {
  getConfigs: () => request<ChatConfigItem[]>('/api/chat/configs'),

  sendMessage: (configId: number, messages: ChatMessage[], model?: string): Promise<ChatResponse> =>
    request<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ config_id: configId, messages, model }),
    }),
};

// ========== AI工具箱API ==========
export const toolboxApi = {
  // 文件操作
  searchFiles: (data: { query: string; directory?: string; file_pattern?: string }) =>
    request<any>('/api/toolbox/files/search', { method: 'POST', body: JSON.stringify(data) }),
  searchKeyword: (keyword: string, directory?: string, filePattern?: string) => {
    const params = new URLSearchParams({ keyword });
    if (directory) params.append('directory', directory);
    if (filePattern) params.append('file_pattern', filePattern);
    return request<any>(`/api/toolbox/files/search-keyword?${params}`);
  },
  locateContent: (data: { keyword: string; directory?: string; context_lines?: number }) =>
    request<any>('/api/toolbox/files/locate', { method: 'POST', body: JSON.stringify(data) }),
  findFiles: (params: { pattern: string; directory?: string; use_regex?: string }) =>
    request<any>(`/api/toolbox/files/find?${new URLSearchParams(params as any)}`),
  readFile: (path: string, startLine?: number, endLine?: number) => {
    let url = `/api/toolbox/files/read?path=${encodeURIComponent(path)}`;
    if (startLine !== undefined) url += `&start_line=${startLine}`;
    if (endLine !== undefined) url += `&end_line=${endLine}`;
    return request<any>(url);
  },
  createFile: (data: { path: string; content: string }) =>
    request<any>('/api/toolbox/files/create', { method: 'POST', body: JSON.stringify(data) }),
  deleteFile: (path: string) =>
    request<any>(`/api/toolbox/files/delete?path=${encodeURIComponent(path)}&confirm=true`, { method: 'DELETE' }),
  updateFile: (data: { path: string; content: string }) =>
    request<any>('/api/toolbox/files/update', { method: 'PUT', body: JSON.stringify(data) }),
  // MCP工具
  getMcpTools: () => request<any>('/api/toolbox/mcp/tools'),
  executeMcpTool: (data: { tool_name: string; parameters: Record<string, any>; require_confirmation?: boolean }) =>
    request<any>('/api/toolbox/mcp/execute', { method: 'POST', body: JSON.stringify(data) }),
  // 智能体任务
  suggestTask: (data: { agent_id: number; task_name: string; task_description: string; priority?: number; parameters?: Record<string, any> }) =>
    request<any>('/api/toolbox/agent-task', { method: 'POST', body: JSON.stringify(data) }),
  confirmTask: (id: number) =>
    request<any>(`/api/toolbox/agent-task/${id}/confirm`, { method: 'PUT' }),
  modifyTask: (id: number, data: { task_name?: string; task_description?: string; priority?: number; parameters?: Record<string, any>; modification_prompt?: string }) =>
    request<any>(`/api/toolbox/agent-task/${id}/modify`, { method: 'PUT', body: JSON.stringify(data) }),
  getTaskStatus: (id: number) =>
    request<any>(`/api/toolbox/agent-task/${id}/status`),
  // 目录浏览
  browseDirectories: (path?: string) => {
    const params = new URLSearchParams();
    if (path) params.append('path', path);
    return request<{ current_path: string; parent_path: string; directories: { name: string; path: string; type: string }[] }>(`/api/toolbox/directories/browse?${params}`);
  },
};

// ========== Skills API ==========
export const skillsApi = {
  getTree: () => request<any>('/api/skills/tree'),
  getFile: (path: string) => request<any>(`/api/skills/file?path=${encodeURIComponent(path)}`),
  createFile: (data: { path: string; content: string }) =>
    request<any>('/api/skills/file', { method: 'POST', body: JSON.stringify(data) }),
  updateFile: (data: { path: string; content: string }) =>
    request<any>('/api/skills/file', { method: 'PUT', body: JSON.stringify(data) }),
  deleteFile: (path: string) =>
    request<any>(`/api/skills/file?path=${encodeURIComponent(path)}`, { method: 'DELETE' }),
  createDirectory: (path: string) =>
    request<any>('/api/skills/directory', { method: 'POST', body: JSON.stringify({ path }) }),
  deleteDirectory: (path: string) =>
    request<any>(`/api/skills/directory?path=${encodeURIComponent(path)}`, { method: 'DELETE' }),
};

// ========== 数据库连接API ==========
export const dbConnectionApi = {
  list: () => request<any[]>('/api/db-connections'),
  create: (data: { name: string; db_type: string; host: string; port: number; username?: string; password?: string; database_name?: string; extra_params?: Record<string, any> }) =>
    request<any>('/api/db-connections', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: number, data: Record<string, any>) =>
    request<any>(`/api/db-connections/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: number) =>
    request<any>(`/api/db-connections/${id}`, { method: 'DELETE' }),
  test: (id: number) =>
    request<any>(`/api/db-connections/${id}/test`, { method: 'POST' }),
};

// ========== 环境信息API ==========
export const environmentApi = {
  detect: () => request<any>('/api/environment/detect'),
  save: () => request<any>('/api/environment/save', { method: 'POST' }),
  getInfo: () => request<any>('/api/environment/info'),
  update: (data: any) => request<any>('/api/environment/update', { method: 'PUT', body: JSON.stringify(data) }),
  autoDetect: (workspace?: string) => {
    const params = workspace ? `?workspace=${encodeURIComponent(workspace)}` : '';
    return request<any>(`/api/environment/auto${params}`);
  },
  getSummary: (workspace?: string) => {
    const params = workspace ? `?workspace=${encodeURIComponent(workspace)}` : '';
    return request<any>(`/api/environment/summary${params}`);
  },
};
