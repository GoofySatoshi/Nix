from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# 文件搜索
class FileSearchRequest(BaseModel):
    query: str
    directory: Optional[str] = "."
    file_pattern: Optional[str] = "*"


class FileSearchMatch(BaseModel):
    file_path: str
    line_number: int
    line_content: str
    context_before: List[str] = []
    context_after: List[str] = []


class FileSearchResponse(BaseModel):
    matches: List[FileSearchMatch]
    total_count: int


# 文件定位
class FileLocateRequest(BaseModel):
    keyword: str
    directory: Optional[str] = "."
    context_lines: int = 3


# 文件查找
class FileFindResponse(BaseModel):
    files: List[str]
    total_count: int


# 文件读取
class FileReadResponse(BaseModel):
    path: str
    content: str
    total_lines: int


# 文件创建
class FileCreateRequest(BaseModel):
    path: str
    content: str = ""


# 文件修改
class FileUpdateRequest(BaseModel):
    path: str
    content: str


# 通用操作响应
class FileOperationResponse(BaseModel):
    success: bool
    message: str
    path: Optional[str] = None


# ========== MCP工具相关 Schema ==========

class McpToolParameter(BaseModel):
    name: str
    type: str  # string/int/bool/float
    description: str
    required: bool = True
    default: Optional[str] = None

class McpToolInfo(BaseModel):
    name: str
    description: str
    category: str  # file_operations / db_operations / system
    parameters: List[McpToolParameter]
    requires_confirmation: bool = False

class McpToolListResponse(BaseModel):
    tools: List[McpToolInfo]
    total_count: int

class McpExecuteRequest(BaseModel):
    tool_name: str
    parameters: dict
    require_confirmation: bool = False

class McpExecuteResponse(BaseModel):
    success: bool
    tool_name: str
    result: Optional[dict] = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None

# ========== 智能体任务关联 Schema ==========

class AgentTaskSuggestRequest(BaseModel):
    agent_id: int
    task_name: str
    task_description: str
    priority: int = 0
    parameters: Optional[dict] = None

class AgentTaskModifyRequest(BaseModel):
    task_name: Optional[str] = None
    task_description: Optional[str] = None
    priority: Optional[int] = None
    parameters: Optional[dict] = None
    modification_prompt: Optional[str] = None  # 自然语言修改指令

class AgentTaskResponse(BaseModel):
    id: int
    agent_id: int
    task_name: str
    task_description: str
    status: str  # pending_confirmation / confirmed / running / completed / failed / cancelled
    priority: int
    parameters: Optional[dict] = None
    result: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

class AgentTaskStatusResponse(BaseModel):
    id: int
    status: str
    progress: Optional[float] = None  # 0.0 ~ 1.0
    current_step: Optional[str] = None
    execution_log: Optional[str] = None
    result: Optional[dict] = None


# ========== 终端操控 Schema ==========

class TerminalExecuteRequest(BaseModel):
    command: str
    working_directory: Optional[str] = None
    timeout: int = 30  # 默认30秒超时


class TerminalExecuteResponse(BaseModel):
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    execution_time_ms: float


# ========== 关键字搜索（按文件分组）Schema ==========

class FileKeywordMatch(BaseModel):
    file_path: str
    line_numbers: List[int]
    preview_lines: List[str] = []


class FileKeywordSearchResponse(BaseModel):
    keyword: str
    matches: List[FileKeywordMatch]
    total_files: int
    total_matches: int


# ========== Browser-Use 浏览器操控 Schema ==========
class BrowserNavigateRequest(BaseModel):
    url: str
    wait_load: bool = True

class BrowserClickRequest(BaseModel):
    selector: str
    wait_after: int = 1  # 点击后等待秒数

class BrowserTypeRequest(BaseModel):
    selector: str
    text: str

class BrowserExtractRequest(BaseModel):
    selector: Optional[str] = None  # 为空则提取整个页面

class BrowserScreenshotRequest(BaseModel):
    full_page: bool = False

class BrowserActionResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None  # 可能包含 screenshot(base64), extracted_text 等
