from pydantic import BaseModel
from typing import List, Optional, Dict


class MemoryItem(BaseModel):
    category: str
    content: str


class MemoryListResponse(BaseModel):
    agent_name: str
    memories: List[Dict]
    raw_content: str
    last_updated: Optional[str] = None


class MemoryAddRequest(BaseModel):
    category: str
    content: str
    workspace: Optional[str] = None  # 新增


class MemoryDeleteRequest(BaseModel):
    category: str
    content: str
    workspace: Optional[str] = None  # 新增


class MemoryUpdateRequest(BaseModel):
    category: str
    old_content: str
    new_content: str
    workspace: Optional[str] = None  # 新增


class MemoryRefineRequest(BaseModel):
    config_id: Optional[int] = None  # 指定LLM配置，不指定则用默认
    model: Optional[str] = None  # 指定模型


class MemoryRefineResponse(BaseModel):
    success: bool
    message: str
    refined_memories: List[Dict]
    raw_content: str


class MemoryOperationResponse(BaseModel):
    success: bool
    message: str
