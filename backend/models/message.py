from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from models.database import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=False)  # user / assistant / system
    content = Column(Text, nullable=False)
    tool_calls = Column(JSON, nullable=True)
    intent = Column(String, nullable=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    model_name = Column(String, nullable=True)
    config_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
