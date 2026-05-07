"""
SharedContext - Agent 间共享上下文

提供 Agent 之间的共享状态存储，包括：
- 当前任务上下文
- 项目信息
- Agent 间共享的临时数据
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TaskContext:
    """单个任务的上下文"""
    task_id: str
    description: str
    status: str = "pending"
    assigned_agent: Optional[str] = None
    subtasks: list[dict] = field(default_factory=list)
    results: dict = field(default_factory=dict)
    shared_data: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class SharedContext:
    """
    Agent 间共享上下文
    
    线程安全的共享状态存储，所有 Agent 都可以读写。
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self._task_contexts: dict[str, TaskContext] = {}
        self._global_data: dict[str, Any] = {}  # 全局共享数据
        self._agent_states: dict[str, dict] = {}  # Agent 状态
        self._project_info: dict[str, Any] = {}  # 项目信息
        logger.info("SharedContext 初始化完成")

    # ---- 任务上下文 ----

    async def create_task_context(
        self, task_id: str, description: str, assigned_agent: Optional[str] = None
    ) -> TaskContext:
        """创建任务上下文"""
        async with self._lock:
            ctx = TaskContext(
                task_id=task_id,
                description=description,
                assigned_agent=assigned_agent,
            )
            self._task_contexts[task_id] = ctx
            logger.info(f"任务上下文已创建: {task_id}")
            return ctx

    async def get_task_context(self, task_id: str) -> Optional[TaskContext]:
        """获取任务上下文"""
        return self._task_contexts.get(task_id)

    async def update_task_status(self, task_id: str, status: str):
        """更新任务状态"""
        async with self._lock:
            ctx = self._task_contexts.get(task_id)
            if ctx:
                ctx.status = status

    async def set_task_data(self, task_id: str, key: str, value: Any):
        """设置任务共享数据"""
        async with self._lock:
            ctx = self._task_contexts.get(task_id)
            if ctx:
                ctx.shared_data[key] = value

    async def get_task_data(self, task_id: str, key: str, default: Any = None) -> Any:
        """获取任务共享数据"""
        ctx = self._task_contexts.get(task_id)
        if ctx:
            return ctx.shared_data.get(key, default)
        return default

    async def add_subtask_result(self, task_id: str, subtask_id: str, result: Any):
        """添加子任务结果"""
        async with self._lock:
            ctx = self._task_contexts.get(task_id)
            if ctx:
                ctx.results[subtask_id] = result

    async def get_task_results(self, task_id: str) -> dict:
        """获取任务所有子结果"""
        ctx = self._task_contexts.get(task_id)
        return ctx.results if ctx else {}

    async def cleanup_task(self, task_id: str):
        """清理任务上下文"""
        async with self._lock:
            self._task_contexts.pop(task_id, None)

    # ---- Agent 状态 ----

    async def update_agent_state(self, agent_id: str, state: dict):
        """更新 Agent 状态"""
        async with self._lock:
            self._agent_states[agent_id] = {
                **state,
                "updated_at": time.time(),
            }

    async def get_agent_state(self, agent_id: str) -> dict:
        """获取 Agent 状态"""
        return self._agent_states.get(agent_id, {})

    async def get_all_agent_states(self) -> dict[str, dict]:
        """获取所有 Agent 状态"""
        return dict(self._agent_states)

    async def remove_agent_state(self, agent_id: str):
        """移除 Agent 状态"""
        async with self._lock:
            self._agent_states.pop(agent_id, None)

    # ---- 全局数据 ----

    async def set_global(self, key: str, value: Any):
        """设置全局共享数据"""
        async with self._lock:
            self._global_data[key] = value

    async def get_global(self, key: str, default: Any = None) -> Any:
        """获取全局共享数据"""
        return self._global_data.get(key, default)

    # ---- 项目信息 ----

    async def set_project_info(self, info: dict):
        """设置项目信息"""
        async with self._lock:
            self._project_info = info

    async def get_project_info(self) -> dict:
        """获取项目信息"""
        return dict(self._project_info)

    # ---- 快照 ----

    async def snapshot(self) -> dict:
        """获取当前上下文快照（用于调试/恢复）"""
        async with self._lock:
            return {
                "tasks": {k: {
                    "task_id": v.task_id,
                    "description": v.description,
                    "status": v.status,
                    "assigned_agent": v.assigned_agent,
                    "results_count": len(v.results),
                } for k, v in self._task_contexts.items()},
                "agents": dict(self._agent_states),
                "global_keys": list(self._global_data.keys()),
                "project_info": dict(self._project_info),
            }


# 全局共享上下文
shared_context = SharedContext()
