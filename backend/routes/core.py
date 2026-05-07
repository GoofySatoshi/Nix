"""
Core Routes - 新核心架构的 API 路由

提供：
- 智能体生命周期管理（新架构）
- 任务编排 API
- 消息总线 API
- 共享上下文 API
"""

import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from dependencies.auth import get_current_user
from models import User

router = APIRouter()


# ---- 请求/响应模型 ----

class OrchestrateRequest(BaseModel):
    task_description: str
    task_id: Optional[str] = None

class AgentMessageRequest(BaseModel):
    to_agent: str
    message_type: str = "task_request"
    payload: dict


# ---- 任务编排 ----

@router.post("/orchestrate")
async def orchestrate_task(
    request: OrchestrateRequest,
    current_user: User = Depends(get_current_user),
):
    """通过编排器执行任务（新架构核心入口）"""
    from core.orchestrator import orchestrator
    try:
        result = await orchestrator.execute(
            task_description=request.task_description,
            task_id=request.task_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orchestrate/plans")
async def list_plans(current_user: User = Depends(get_current_user)):
    """列出所有活跃的执行计划"""
    from core.orchestrator import orchestrator
    return orchestrator.list_active_plans()


@router.get("/orchestrate/plans/{task_id}")
async def get_plan_status(task_id: str, current_user: User = Depends(get_current_user)):
    """获取执行计划状态"""
    from core.orchestrator import orchestrator
    status = orchestrator.get_plan_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="计划不存在")
    return status


# ---- 智能体管理（新架构）----

@router.get("/agents")
async def list_core_agents(current_user: User = Depends(get_current_user)):
    """列出所有核心 Agent"""
    from core.bridge import get_core_agents
    agents = get_core_agents()
    return [agent.get_info() for agent in agents.values()]


@router.get("/agents/{agent_id}")
async def get_core_agent(agent_id: str, current_user: User = Depends(get_current_user)):
    """获取核心 Agent 详情"""
    from core.bridge import get_core_agent
    agent = get_core_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return agent.get_info()


@router.post("/agents/{agent_id}/start")
async def start_core_agent(agent_id: str, current_user: User = Depends(get_current_user)):
    """启动核心 Agent"""
    from core.bridge import get_core_agent
    agent = get_core_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    await agent.start()
    return {"status": agent.status.value}


@router.post("/agents/{agent_id}/stop")
async def stop_core_agent(agent_id: str, current_user: User = Depends(get_current_user)):
    """停止核心 Agent"""
    from core.bridge import get_core_agent
    agent = get_core_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    await agent.stop()
    return {"status": agent.status.value}


# ---- 消息总线 ----

@router.get("/message-bus/agents")
async def list_registered_agents(current_user: User = Depends(get_current_user)):
    """列出消息总线上已注册的 Agent"""
    from core.message_bus import message_bus
    return {"agents": message_bus.get_registered_agents()}


@router.get("/message-bus/history")
async def get_message_history(
    agent_id: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    """获取消息历史"""
    from core.message_bus import message_bus
    messages = message_bus.get_history(agent_id=agent_id, limit=limit)
    return [
        {
            "type": m.type.value,
            "from": m.from_agent,
            "to": m.to_agent,
            "payload_keys": list(m.payload.keys()),
            "correlation_id": m.correlation_id,
            "timestamp": m.timestamp.isoformat(),
        }
        for m in messages
    ]


# ---- 共享上下文 ----

@router.get("/context/snapshot")
async def get_context_snapshot(current_user: User = Depends(get_current_user)):
    """获取共享上下文快照"""
    from core.shared_context import shared_context
    return await shared_context.snapshot()


@router.get("/context/agents")
async def get_all_agent_states(current_user: User = Depends(get_current_user)):
    """获取所有 Agent 状态"""
    from core.shared_context import shared_context
    return await shared_context.get_all_agent_states()


@router.get("/context/project")
async def get_project_info(current_user: User = Depends(get_current_user)):
    """获取项目信息"""
    from core.shared_context import shared_context
    return await shared_context.get_project_info()


# ---- 工具注册表 ----

@router.get("/tools")
async def list_tools(current_user: User = Depends(get_current_user)):
    """列出所有可用工具"""
    from core.tool_registry import get_tool_registry
    tools = get_tool_registry()
    return [
        {
            "name": t.name,
            "description": t.description,
            "category": t.category.value,
            "dangerous": t.dangerous,
        }
        for t in tools.list_tools()
    ]
