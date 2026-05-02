from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from models.database import Base

class DbConnection(Base):
    __tablename__ = "db_connections"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # 连接名称
    db_type = Column(String, nullable=False)  # mysql/redis/elasticsearch/postgresql/mongodb
    host = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    username = Column(String, nullable=True)
    password = Column(String, nullable=True)  # 存储时加密
    database_name = Column(String, nullable=True)
    extra_params = Column(JSON, nullable=True)  # 额外配置
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
