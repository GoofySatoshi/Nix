from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class WorkflowStepBase(BaseModel):
    name: str
    description: Optional[str] = None
    order: int

class WorkflowStepCreate(WorkflowStepBase):
    task_id: int

class WorkflowStepUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    order: Optional[int] = None

class WorkflowStepResponse(WorkflowStepBase):
    id: int
    task_id: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
