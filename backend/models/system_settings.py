from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from models.database import Base


class SystemSettings(Base):
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 意图识别模型（留空使用主模型）
    intent_model = Column(String, default="")
    
    # 任务拆分/待办清单生成模型（留空使用主模型）
    plan_model = Column(String, default="")
    
    # 验收标准生成模型（留空使用主模型）
    acceptance_model = Column(String, default="")
    
    # 验收最大循环次数（0=无限制）
    max_acceptance_rounds = Column(Integer, default=3)
    
    # 工具调用最大迭代次数（每轮任务，默认30）
    max_tool_iterations = Column(Integer, default=30)
    
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
