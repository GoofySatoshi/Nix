from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func
from models.database import Base


class EnvironmentInfo(Base):
    __tablename__ = "environment_info"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)

    # 设备信息
    device_model = Column(String, nullable=True)       # 设备型号
    os_name = Column(String, nullable=True)            # 操作系统名称 (macOS/Linux/Windows)
    os_version = Column(String, nullable=True)         # 操作系统版本
    architecture = Column(String, nullable=True)       # CPU架构 (arm64/x86_64)
    shell = Column(String, nullable=True)              # 默认Shell
    hostname = Column(String, nullable=True)           # 主机名

    # 技术栈检测结果
    tech_stack = Column(JSON, nullable=True)           # 检测到的技术栈 {"python": "3.10.x", "node": "18.x", ...}
    package_managers = Column(JSON, nullable=True)     # 可用包管理器 ["brew", "npm", "pip"]

    # 终端命令兼容性
    terminal_notes = Column(JSON, nullable=True)       # 终端注意事项列表

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
