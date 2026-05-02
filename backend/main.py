from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from models import Base
from models.database import engine
from services.llm_service import load_llm_from_db

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 启动时从数据库加载 LLM 配置
load_llm_from_db()

app = FastAPI()

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.get("/")
def read_root():
    return {"message": "多智能体协作系统后端API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # 处理接收到的消息
            await manager.broadcast(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# 导入路由
from routes import auth, agents, tasks, workflow, settings, chat, toolbox, db_connections, skills, environment

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(workflow.router, prefix="/api/workflow", tags=["workflow"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(toolbox.router, prefix="/api/toolbox", tags=["toolbox"])
app.include_router(db_connections.router, prefix="/api/db-connections", tags=["db-connections"])
app.include_router(skills.router, prefix="/api/skills", tags=["skills"])
app.include_router(environment.router, prefix="/api/environment", tags=["environment"])

# 导出manager供其他模块使用
__all__ = ["app", "manager"]