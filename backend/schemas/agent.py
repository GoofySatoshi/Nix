from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any

class AgentBase(BaseModel):
    name: str
    type: str
    personality: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    config_id: Optional[int] = None
    avatar: Optional[str] = None

class AgentCreate(AgentBase):
    pass

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    personality: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    config_id: Optional[int] = None
    avatar: Optional[str] = None

class AgentResponse(AgentBase):
    id: int
    status: str
    config_name: Optional[str] = None
    avatar: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AgentDispatchRequest(BaseModel):
    source_agent_id: int
    target_agent_id: int
    task_name: str
    task_description: str
    parameters: Optional[dict] = None
    priority: int = 0

class AgentDispatchResponse(BaseModel):
    success: bool
    message: str
    task_id: Optional[int] = None
    source_agent_id: int
    target_agent_id: int

class AgentScheduleInfo(BaseModel):
    agent_id: int
    agent_name: str
    agent_type: str
    status: str
    config_id: Optional[int] = None
    config_name: Optional[str] = None
    current_tasks: int
    available: bool

class AutoScheduleRequest(BaseModel):
    task_name: str
    task_description: str
    preferred_agent_type: Optional[str] = None
    parameters: Optional[dict] = None
    priority: int = 0

class AutoScheduleResponse(BaseModel):
    success: bool
    message: str
    task_id: Optional[int] = None
    assigned_agent_id: Optional[int] = None
    assigned_agent_name: Optional[str] = None