from pydantic import BaseModel
from typing import Optional

class SystemSettingsResponse(BaseModel):
    id: int
    intent_model: str = ""
    plan_model: str = ""
    acceptance_model: str = ""
    max_acceptance_rounds: int = 3
    max_tool_iterations: int = 30
    
    class Config:
        from_attributes = True

class SystemSettingsUpdate(BaseModel):
    intent_model: Optional[str] = None
    plan_model: Optional[str] = None
    acceptance_model: Optional[str] = None
    max_acceptance_rounds: Optional[int] = None
    max_tool_iterations: Optional[int] = None
