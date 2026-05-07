from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
import os
import logging
from logging.handlers import RotatingFileHandler

# 确保日志目录存在
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'app.log')

# 配置全局日志 - 同时输出到控制台和文件
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),  # 控制台输出
        RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
    ]
)

from models import Base
from models.database import engine
from services.llm_service import load_llm_from_db

logger = logging.getLogger(__name__)

# 简单的数据库迁移：为 api_key_configs 表添加缺失列（如果不存在）
def _migrate_db():
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(api_key_configs)"))
            columns = [row[1] for row in result]
            if 'max_acceptance_rounds' not in columns:
                conn.execute(text("ALTER TABLE api_key_configs ADD COLUMN max_acceptance_rounds INTEGER DEFAULT 3"))
                conn.commit()
                logger.info("已添加 max_acceptance_rounds 列到 api_key_configs 表")
            if 'intent_model' not in columns:
                conn.execute(text("ALTER TABLE api_key_configs ADD COLUMN intent_model VARCHAR DEFAULT ''"))
                conn.commit()
                logger.info("已添加 intent_model 列到 api_key_configs 表")
            # tasks 表迁移
            result2 = conn.execute(text("PRAGMA table_info(tasks)"))
            task_columns = [row[1] for row in result2]
            if 'acceptance_criteria' not in task_columns:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN acceptance_criteria TEXT"))
                conn.commit()
                logger.info("已添加 acceptance_criteria 列到 tasks 表")
            if 'acceptance_status' not in task_columns:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN acceptance_status VARCHAR DEFAULT 'pending'"))
                conn.commit()
                logger.info("已添加 acceptance_status 列到 tasks 表")
            if 'acceptance_attempts' not in task_columns:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN acceptance_attempts INTEGER DEFAULT 0"))
                conn.commit()
                logger.info("已添加 acceptance_attempts 列到 tasks 表")
            # system_settings 表迁移
            result3 = conn.execute(text("PRAGMA table_info(system_settings)"))
            ss_columns = [row[1] for row in result3]
            if 'max_tool_iterations' not in ss_columns:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN max_tool_iterations INTEGER DEFAULT 30"))
                conn.commit()
                logger.info("已添加 max_tool_iterations 列到 system_settings 表")
    except Exception as e:
        logger.warning(f"数据库迁移检查失败（可能表尚不存在）: {e}")

_migrate_db()

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 启动时从数据库加载 LLM 配置
load_llm_from_db()

app = FastAPI()

# AI 专用线程池（用于 LLM 长时间调用，不阻塞 uvicorn 事件循环）
ai_thread_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ai-worker")
app.state.ai_thread_pool = ai_thread_pool

@app.on_event("startup")
async def startup_event():
    # 增大 uvicorn 默认线程限制，确保有足够线程处理并发请求
    import anyio
    limiter = anyio.to_thread.current_default_thread_limiter()
    limiter.total_tokens = 40
    logger.info(f"已设置默认线程限制为 {limiter.total_tokens}")

    from services.task_dispatcher import dispatcher
    dispatcher.start()
    logger.info("任务调度器已随应用启动")

    # 初始化新核心基础设施
    from core.bridge import initialize_core
    workspace = os.environ.get("NIX_WORKSPACE", os.path.dirname(__file__))
    llm_config = None
    try:
        from services.llm_service import llm as default_llm
        if default_llm:
            # 从现有 LLM 服务提取配置
            llm_config = {
                "api_key": getattr(default_llm, 'openai_api_key', ''),
                "model": getattr(default_llm, 'model_name', 'gpt-3.5-turbo'),
                "base_url": getattr(default_llm, 'openai_api_base', None),
            }
    except Exception:
        pass
    await initialize_core(workspace_root=workspace, llm_config=llm_config)
    logger.info("新核心基础设施已初始化")

@app.on_event("shutdown")
async def shutdown_event():
    ai_thread_pool.shutdown(wait=False)
    logger.info("AI 线程池已关闭")

    # 关闭新核心
    from core.bridge import shutdown_core
    await shutdown_core()
    logger.info("核心基础设施已关闭")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
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
from routes import auth, agents, tasks, workflow, settings, chat, toolbox, db_connections, skills, environment, memories, messages
from routes.system_settings import router as system_settings_router
from routes.core import router as core_router

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(workflow.router, prefix="/api/workflow", tags=["workflow"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(toolbox.router, prefix="/api/toolbox", tags=["toolbox"])
app.include_router(db_connections.router, prefix="/api/db-connections", tags=["db-connections"])
app.include_router(skills.router, prefix="/api/skills", tags=["skills"])
app.include_router(memories.router, prefix="/api/memories", tags=["memories"])
app.include_router(environment.router, prefix="/api/environment", tags=["environment"])
app.include_router(messages.router, prefix="/api/messages", tags=["messages"])
app.include_router(system_settings_router, prefix="/api/system-settings", tags=["system-settings"])
app.include_router(core_router, prefix="/api/core", tags=["core"])

# 导出manager供其他模块使用
__all__ = ["app", "manager"]