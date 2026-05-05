from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.sql import func
from models.database import Base

class ApiKeyConfig(Base):
    __tablename__ = "api_key_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)                    # 配置名称，如 "OpenAI 生产环境"
    vendor = Column(String, nullable=False, default="openai") # 厂商: openai / azure / xiaomi / custom
    model_name = Column(String, nullable=False, default="gpt-3.5-turbo")  # 默认/主模型（保留兼容）
    model_list = Column(JSON, nullable=True)                  # 模型列表，如 ["gpt-4", "gpt-3.5-turbo", "gpt-4o"]
    api_key = Column(Text, nullable=False, default="")
    api_base_url = Column(String, nullable=True, default="")
    model_list_url = Column(String, nullable=True, default="") # 获取模型列表的接口地址
    intent_model = Column(String, nullable=True, default="")  # 意图识别使用的模型名称，为空时使用主模型
    is_default = Column(Boolean, default=False)              # 是否默认使用
    max_acceptance_rounds = Column(Integer, default=3)        # 验收最大循环次数
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
