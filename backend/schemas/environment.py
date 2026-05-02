from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime


class EnvironmentDetectResponse(BaseModel):
    device_model: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    architecture: Optional[str] = None
    shell: Optional[str] = None
    hostname: Optional[str] = None
    tech_stack: Dict[str, str] = {}
    package_managers: List[str] = []
    terminal_notes: List[str] = []


class EnvironmentInfoResponse(EnvironmentDetectResponse):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EnvironmentUpdateRequest(BaseModel):
    device_model: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    tech_stack: Optional[Dict[str, str]] = None
    terminal_notes: Optional[List[str]] = None
