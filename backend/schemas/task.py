from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class TaskBase(BaseModel):
    name: str
    description: Optional[str] = None
    agent_id: Optional[int] = None
    dependencies: Optional[List[int]] = None
    priority: Optional[int] = 0
    mermaid_syntax: Optional[str] = None

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    dependencies: Optional[List[int]] = None
    priority: Optional[int] = None
    mermaid_syntax: Optional[str] = None

class TaskResponse(TaskBase):
    id: int
    status: str
    result: Optional[dict] = None
    execution_log: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True