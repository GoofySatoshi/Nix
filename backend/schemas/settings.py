from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, List

class ApiKeyConfigCreate(BaseModel):
    name: str
    vendor: str = "openai"
    model_name: str = "gpt-3.5-turbo"
    model_list: Optional[List[str]] = None  # 可用模型列表
    api_key: str
    api_base_url: Optional[str] = ""
    model_list_url: Optional[str] = ""
    is_default: bool = False

class ApiKeyConfigUpdate(BaseModel):
    name: Optional[str] = None
    vendor: Optional[str] = None
    model_name: Optional[str] = None
    model_list: Optional[List[str]] = None  # 可用模型列表
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None
    model_list_url: Optional[str] = None
    is_default: Optional[bool] = None

class ApiKeyConfigResponse(BaseModel):
    id: int
    name: str
    vendor: str
    model_name: str
    model_list: Optional[List[str]] = None  # 可用模型列表
    api_key: str                        # 完整 key，仅 GET 单个时返回
    api_base_url: str
    model_list_url: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ApiKeyConfigListResponse(BaseModel):
    """列表返回完整 API key"""
    id: int
    name: str
    vendor: str
    model_name: str
    model_list: Optional[List[str]] = None  # 可用模型列表
    api_key: str                        # 完整 key
    api_base_url: str
    model_list_url: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# -------- 获取模型列表 --------

class FetchModelsRequest(BaseModel):
    model_list_url: str
    api_key: str
    vendor: str = "openai"

class FetchModelsResponse(BaseModel):
    models: list[str]
    raw_count: int
    vendor: str
