from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Any


class MessageBase(BaseModel):
    agent_id: Optional[int] = None
    role: str
    content: str
    tool_calls: Optional[List[Any]] = None
    intent: Optional[str] = None
    task_id: Optional[int] = None
    model_name: Optional[str] = None
    config_name: Optional[str] = None


class MessageCreate(MessageBase):
    pass


class MessageBatchCreate(BaseModel):
    messages: List[MessageCreate]


class MessageResponse(MessageBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True
