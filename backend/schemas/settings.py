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
    intent_model: Optional[str] = ""  # 意图识别使用的模型名称，为空时使用主模型
    is_default: bool = False
    max_acceptance_rounds: Optional[int] = 3

class ApiKeyConfigUpdate(BaseModel):
    name: Optional[str] = None
    vendor: Optional[str] = None
    model_name: Optional[str] = None
    model_list: Optional[List[str]] = None  # 可用模型列表
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None
    model_list_url: Optional[str] = None
    intent_model: Optional[str] = None  # 意图识别使用的模型名称，为空时使用主模型
    is_default: Optional[bool] = None
    max_acceptance_rounds: Optional[int] = None

class ApiKeyConfigResponse(BaseModel):
    id: int
    name: str
    vendor: str
    model_name: str
    model_list: Optional[List[str]] = None  # 可用模型列表
    api_key: str                        # 完整 key，仅 GET 单个时返回
    api_base_url: str
    model_list_url: str
    intent_model: Optional[str] = ""  # 意图识别使用的模型名称，为空时使用主模型
    is_default: bool
    max_acceptance_rounds: Optional[int] = 3
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
    intent_model: Optional[str] = ""  # 意图识别使用的模型名称，为空时使用主模型
    is_default: bool
    max_acceptance_rounds: Optional[int] = 3
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
