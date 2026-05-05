from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from models.database import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    ai_reply = Column(Text, nullable=True)  # AI 完整回复内容
    status = Column(String, default="pending")
    agent_id = Column(Integer, nullable=True)
    dependencies = Column(JSON, nullable=True)  # 依赖的任务ID列表
    priority = Column(Integer, default=0)  # 任务优先级，数字越大优先级越高
    mermaid_syntax = Column(Text, nullable=True)  # Mermaid语法，用于描述任务执行步骤
    result = Column(JSON, nullable=True)  # 智能体执行结果
    execution_log = Column(Text, nullable=True)  # 执行过程日志
    intent_tag = Column(String, nullable=True)  # 意图标签（来自意图识别）
    progress = Column(Integer, default=0)  # 执行进度 0-100
    progress_message = Column(String, nullable=True)  # 进度描述
    acceptance_criteria = Column(JSON, nullable=True)      # 验收标准列表 [{"id":1,"description":"...","check_method":"..."}]
    acceptance_status = Column(String, default="pending")   # pending/in_review/passed/failed
    acceptance_attempts = Column(Integer, default=0)        # 验收尝试次数
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())