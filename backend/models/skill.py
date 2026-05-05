from sqlalchemy import Column, Integer, String, Text, JSON, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from models.database import Base


class Skill(Base):
    __tablename__ = "skills"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    scope = Column(String, nullable=False)  # "agent" 或 "project"
    
    # 检索相关
    keywords = Column(JSON, nullable=True)   # ["关键词1", "关键词2"]
    category = Column(String, nullable=True)  # 分类标签
    
    # 关联
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    
    # 元数据
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
