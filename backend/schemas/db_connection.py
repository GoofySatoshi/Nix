from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime

class DbConnectionBase(BaseModel):
    name: str
    db_type: str  # mysql/redis/elasticsearch/postgresql/mongodb
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    database_name: Optional[str] = None
    extra_params: Optional[dict] = None

class DbConnectionCreate(DbConnectionBase):
    pass

class DbConnectionUpdate(DbConnectionBase):
    name: Optional[str] = None
    db_type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None

class DbConnectionResponse(DbConnectionBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    password: Optional[str] = "******"  # 不返回明文密码
    
    @field_validator('password', mode='before')
    @classmethod
    def mask_password(cls, v):
        return "******" if v else None
    
    class Config:
        from_attributes = True

class DbConnectionTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: Optional[float] = None
