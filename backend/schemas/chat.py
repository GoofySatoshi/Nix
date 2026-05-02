from pydantic import BaseModel
from typing import Optional, List

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    config_id: int
    messages: list[ChatMessage]
    model: Optional[str] = None  # 可选，指定使用哪个模型，不指定则用默认

class ChatResponse(BaseModel):
    reply: str
    model_name: str
    vendor: str
    config_name: str

class ChatConfigItem(BaseModel):
    id: int
    name: str
    vendor: str
    model_name: str  # 默认模型
    model_list: Optional[List[str]] = None  # 所有可用模型
    is_default: bool
