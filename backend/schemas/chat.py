from pydantic import BaseModel
from typing import Optional, List

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str

class ChatRequest(BaseModel):
    config_id: Optional[int] = None
    messages: list[ChatMessage]
    model: Optional[str] = None  # 可选，指定使用哪个模型，不指定则用默认
    agent_id: Optional[int] = None  # 新增：关联智能体，实现对话隔离

class ToolCallTrace(BaseModel):
    tool_name: str
    parameters: dict
    result: str
    success: bool = True

class ChatResponse(BaseModel):
    reply: str
    model_name: str
    vendor: str
    config_name: str
    tool_calls: List[ToolCallTrace] = []  # 工具调用轨迹
    intent: str = ""  # 识别的用户意图（原始值）
    intent_display_name: str = ""  # 意图的中文显示名称
    task_id: Optional[int] = None  # 关联的任务ID

class ChatConfigItem(BaseModel):
    id: int
    name: str
    vendor: str
    model_name: str  # 默认模型
    model_list: Optional[List[str]] = None  # 所有可用模型
    is_default: bool
