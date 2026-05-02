from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.sql import func
from models.database import Base

class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    personality = Column(Text, nullable=True)
    config = Column(JSON, nullable=True)
    config_id = Column(Integer, ForeignKey("api_key_configs.id"), nullable=True)
    avatar = Column(String, nullable=True)
    status = Column(String, default="stopped")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())