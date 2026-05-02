from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from models.database import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="pending")
    agent_id = Column(Integer, nullable=True)
    dependencies = Column(JSON, nullable=True)  # 依赖的任务ID列表
    priority = Column(Integer, default=0)  # 任务优先级，数字越大优先级越高
    mermaid_syntax = Column(Text, nullable=True)  # Mermaid语法，用于描述任务执行步骤
    result = Column(JSON, nullable=True)  # 智能体执行结果
    execution_log = Column(Text, nullable=True)  # 执行过程日志
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())