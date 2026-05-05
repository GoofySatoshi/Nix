from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Agent, get_db, User, ApiKeyConfig, Task
from schemas.agent import (
    AgentCreate, AgentUpdate, AgentResponse,
    AgentDispatchRequest, AgentDispatchResponse,
    AgentScheduleInfo, AutoScheduleRequest, AutoScheduleResponse
)
from schemas.task import TaskCreate
from services.agent_manager import create_agent, get_agent, get_agents, update_agent, delete_agent, start_agent, stop_agent, get_agent_types
from services.task_executor import create_task
from services.task_dispatcher import dispatcher
from dependencies.auth import get_current_user

router = APIRouter()

def _enrich_agent_response(db: Session, agent: Agent) -> AgentResponse:
    """为Agent响应附加config_name"""
    config_name = None
    if agent.config_id:
        config = db.query(ApiKeyConfig).filter(ApiKeyConfig.id == agent.config_id).first()
        if config:
            config_name = config.name
    response = AgentResponse(
        id=agent.id,
        name=agent.name,
        type=agent.type,
        personality=agent.personality,
        config=agent.config,
        config_id=agent.config_id,
        config_name=config_name,
        status=agent.status,
        avatar=agent.avatar,
        created_at=agent.created_at,
        updated_at=agent.updated_at
    )
    return response

@router.get("", response_model=list[AgentResponse])
def get_agent_list(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    agents = get_agents(db)
    return [_enrich_agent_response(db, a) for a in agents]

@router.post("", response_model=AgentResponse)
def create_agent_endpoint(agent: AgentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_agent = create_agent(db, agent)
    return _enrich_agent_response(db, db_agent)

@router.get("/types")
def get_agent_types_endpoint(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    types = get_agent_types(db)
    return {"types": types}

@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent_endpoint(agent_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_agent = get_agent(db, agent_id)
    if not db_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    return _enrich_agent_response(db, db_agent)

@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent_endpoint(agent_id: int, agent: AgentUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_agent = update_agent(db, agent_id, agent)
    if not db_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    return _enrich_agent_response(db, db_agent)

@router.delete("/{agent_id}")
def delete_agent_endpoint(agent_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    success = delete_agent(db, agent_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    return {"message": "Agent deleted successfully"}

@router.post("/{agent_id}/start")
def start_agent_endpoint(agent_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_agent = start_agent(db, agent_id)
    if not db_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    return {"status": db_agent.status}

@router.post("/{agent_id}/stop")
def stop_agent_endpoint(agent_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_agent = stop_agent(db, agent_id)
    if not db_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    return {"status": db_agent.status}

@router.get("/{agent_id}/model")
def get_agent_model(agent_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取智能体绑定的模型配置详情"""
    db_agent = get_agent(db, agent_id)
    if not db_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    if not db_agent.config_id:
        return {"message": "Agent has no model config bound", "config": None}
    config = db.query(ApiKeyConfig).filter(ApiKeyConfig.id == db_agent.config_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model config not found"
        )
    return {
        "agent_id": agent_id,
        "config_id": config.id,
        "name": config.name,
        "vendor": config.vendor,
        "model_name": config.model_name,
        "api_base_url": config.api_base_url,
        "model_list_url": config.model_list_url,
        "is_default": config.is_default
    }

@router.post("/{agent_id}/dispatch", response_model=AgentDispatchResponse)
def dispatch_to_agent(
    agent_id: int,
    request: AgentDispatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """智能体向另一个智能体派发任务"""
    if request.source_agent_id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_agent_id must match the path agent_id"
        )
    target_agent = get_agent(db, request.target_agent_id)
    if not target_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target agent not found"
        )
    if target_agent.status != "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target agent is not running"
        )
    task = create_task(db, TaskCreate(
        name=request.task_name,
        description=request.task_description,
        agent_id=request.target_agent_id,
        dependencies=[],
        priority=request.priority
    ))
    return AgentDispatchResponse(
        success=True,
        message="Task dispatched successfully",
        task_id=task.id,
        source_agent_id=request.source_agent_id,
        target_agent_id=request.target_agent_id
    )

@router.get("/schedule/available", response_model=list[AgentScheduleInfo])
def get_available_agents(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取所有可调度的智能体列表（含工作负载信息）"""
    agents = db.query(Agent).filter(Agent.status == "running").all()
    result = []
    for agent in agents:
        current_tasks = db.query(func.count(Task.id)).filter(
            Task.agent_id == agent.id,
            Task.status.in_(["pending", "running"])
        ).scalar() or 0
        config_name = None
        if agent.config_id:
            config = db.query(ApiKeyConfig).filter(ApiKeyConfig.id == agent.config_id).first()
            if config:
                config_name = config.name
        result.append(AgentScheduleInfo(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_type=agent.type,
            status=agent.status,
            config_id=agent.config_id,
            config_name=config_name,
            current_tasks=current_tasks,
            available=(current_tasks < 5)
        ))
    return result

@router.post("/schedule/auto", response_model=AutoScheduleResponse)
def auto_schedule_task(
    request: AutoScheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """自动调度：根据任务需求自动选择最合适的智能体"""
    query = db.query(Agent).filter(Agent.status == "running")
    if request.preferred_agent_type:
        query = query.filter(Agent.type == request.preferred_agent_type)
    candidates = query.all()
    if not candidates:
        return AutoScheduleResponse(
            success=False,
            message="No available agent found for the task",
            task_id=None,
            assigned_agent_id=None,
            assigned_agent_name=None
        )
    # 选择当前任务数最少的智能体
    best_agent = None
    min_tasks = float("inf")
    for agent in candidates:
        current_tasks = db.query(func.count(Task.id)).filter(
            Task.agent_id == agent.id,
            Task.status.in_(["pending", "running"])
        ).scalar() or 0
        if current_tasks < min_tasks:
            min_tasks = current_tasks
            best_agent = agent
    if not best_agent:
        return AutoScheduleResponse(
            success=False,
            message="No suitable agent found",
            task_id=None,
            assigned_agent_id=None,
            assigned_agent_name=None
        )
    task = create_task(db, TaskCreate(
        name=request.task_name,
        description=request.task_description,
        agent_id=best_agent.id,
        dependencies=[],
        priority=request.priority
    ))
    return AutoScheduleResponse(
        success=True,
        message="Task auto-scheduled successfully",
        task_id=task.id,
        assigned_agent_id=best_agent.id,
        assigned_agent_name=best_agent.name
    )

@router.post("/dispatcher/start")
def start_dispatcher(current_user: User = Depends(get_current_user)):
    """启动任务调度器"""
    dispatcher.start()
    return {"success": True, "message": "调度器已启动"}

@router.post("/dispatcher/stop")
def stop_dispatcher(current_user: User = Depends(get_current_user)):
    """停止任务调度器"""
    dispatcher.stop()
    return {"success": True, "message": "调度器已停止"}

@router.get("/dispatcher/status")
def dispatcher_status(current_user: User = Depends(get_current_user)):
    """获取调度器状态"""
    return {"running": dispatcher._running}