"""
TaskOrchestrator - 任务编排器

替代原来的 TaskDispatcher（轮询DB的方式）。
提供：
- 任务分解：复杂任务拆成子任务
- 智能分配：根据 Agent 能力和负载分配
- 并行/串行执行
- 结果聚合
- 验收与迭代
"""

import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from core.message_bus import MessageBus, AgentMessage, MessageType, message_bus
from core.shared_context import SharedContext, shared_context
from core.agent_base import Agent, AgentStatus

logger = logging.getLogger(__name__)


@dataclass
class SubTask:
    """子任务"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    assigned_agent: Optional[str] = None
    status: str = "pending"
    result: Any = None
    dependencies: list[str] = field(default_factory=list)


@dataclass
class ExecutionPlan:
    """执行计划"""
    task_id: str
    description: str
    subtasks: list[SubTask] = field(default_factory=list)
    strategy: str = "sequential"  # "sequential" | "parallel" | "dag"


class TaskOrchestrator:
    """
    任务编排器
    
    负责将复杂任务分解为子任务，分配给合适的 Agent，
    监控执行进度，聚合结果。
    """

    def __init__(
        self,
        bus: Optional[MessageBus] = None,
        context: Optional[SharedContext] = None,
    ):
        self._bus = bus or message_bus
        self._context = context or shared_context
        self._agents: dict[str, Agent] = {}  # 已注册的 Agent
        self._active_plans: dict[str, ExecutionPlan] = {}
        self._llm = None
        logger.info("TaskOrchestrator 初始化完成")

    def register_agent(self, agent: Agent):
        """注册 Agent 到编排器"""
        self._agents[agent.id] = agent
        logger.info(f"Agent {agent.name} 已注册到 Orchestator")

    def unregister_agent(self, agent_id: str):
        """注销 Agent"""
        self._agents.pop(agent_id, None)

    def set_llm(self, llm):
        """设置 LLM（用于任务分解和结果聚合）"""
        self._llm = llm

    async def execute(self, task_description: str, task_id: Optional[str] = None) -> dict:
        """
        执行任务的完整生命周期
        
        1. 分解：复杂任务拆成子任务
        2. 分配：根据能力+负载选择 Agent
        3. 执行：并行/串行执行子任务
        4. 聚合：合并子任务结果
        5. 验收：检查是否满足要求
        """
        task_id = task_id or str(uuid.uuid4())
        logger.info(f"开始编排任务: {task_id} - {task_description[:100]}")

        # 1. 分解
        plan = await self._decompose(task_id, task_description)
        self._active_plans[task_id] = plan

        # 2. 分配
        assignments = await self._assign(plan)

        # 3. 执行
        results = await self._execute_plan(plan)

        # 4. 聚合
        aggregated = await self._aggregate(task_description, results)

        # 5. 清理
        self._active_plans.pop(task_id, None)

        return {
            "task_id": task_id,
            "success": all(r.get("success") for r in results),
            "output": aggregated,
            "subtask_results": results,
            "agents_used": [s.assigned_agent for s in plan.subtasks if s.assigned_agent],
        }

    async def _decompose(self, task_id: str, description: str) -> ExecutionPlan:
        """任务分解"""
        plan = ExecutionPlan(task_id=task_id, description=description)

        if not self._llm:
            # 无 LLM 时作为单个任务
            plan.subtasks = [SubTask(
                name="执行任务",
                description=description,
            )]
            plan.strategy = "sequential"
            return plan

        # 获取可用 Agent 信息
        agent_info = []
        for aid, agent in self._agents.items():
            caps = agent.capabilities
            agent_info.append({
                "id": aid,
                "name": agent.name,
                "capabilities": caps.name,
                "intent_tags": caps.intent_tags,
                "status": agent.status.value,
            })

        from langchain_core.messages import SystemMessage, HumanMessage

        system = f"""你是一个任务分解专家。将复杂任务分解为可分配给不同智能体的子任务。

## 可用智能体
{json.dumps(agent_info, ensure_ascii=False, indent=2)}

## 规则
1. 每个子任务应该能由一个独立的智能体完成
2. 指定每个子任务最适合的 agent_id
3. 识别子任务间的依赖关系
4. 选择执行策略：sequential（串行）、parallel（并行）、dag（有依赖的图）

## 输出格式
严格 JSON，不要其他文字：
{{"subtasks": [{{"name": "子任务名", "description": "详细描述", "agent_id": "智能体ID或null", "dependencies": []}}], "strategy": "sequential"}}"""

        try:
            response = self._llm.invoke([
                SystemMessage(content=system),
                HumanMessage(content=f"任务: {description}"),
            ])
            content = response.content.strip()

            # 提取 JSON
            json_match = re.search(r'```(?:json)?\s*(.*?)```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1).strip()
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)

            parsed = json.loads(content)
            for st in parsed.get("subtasks", []):
                plan.subtasks.append(SubTask(
                    name=st.get("name", ""),
                    description=st.get("description", ""),
                    assigned_agent=st.get("agent_id"),
                    dependencies=st.get("dependencies", []),
                ))
            plan.strategy = parsed.get("strategy", "sequential")
        except Exception as e:
            logger.warning(f"任务分解失败: {e}，使用单任务模式")
            plan.subtasks = [SubTask(name="执行任务", description=description)]

        return plan

    async def _assign(self, plan: ExecutionPlan) -> dict[str, str]:
        """为未分配的子任务选择 Agent"""
        assignments = {}

        for subtask in plan.subtasks:
            if subtask.assigned_agent and subtask.assigned_agent in self._agents:
                assignments[subtask.id] = subtask.assigned_agent
                continue

            # 自动分配：找最匹配且负载最低的 Agent
            best_agent = self._find_best_agent(subtask)
            if best_agent:
                subtask.assigned_agent = best_agent
                assignments[subtask.id] = best_agent
            else:
                logger.warning(f"子任务 {subtask.name} 无可用 Agent")

        return assignments

    def _find_best_agent(self, subtask: SubTask) -> Optional[str]:
        """为子任务选择最佳 Agent（基于能力匹配 + 负载均衡）"""
        candidates = []
        desc = (subtask.description + " " + subtask.name).lower()

        # 意图关键词 → Agent 能力映射
        capability_keywords = {
            "chat": ["对话", "聊天", "问答", "解释", "分析", "review", "审查", "说明"],
            "developer": ["创建", "写", "代码", "文件", "修改", "删除", "执行", "命令", "开发", "实现", "配置"],
        }

        for aid, agent in self._agents.items():
            if agent.status in (AgentStatus.STOPPED, AgentStatus.ERROR):
                continue

            caps = agent.capabilities
            active_tasks = len(self._get_agent_active_tasks(aid))

            # 检查并发限制
            if active_tasks >= caps.max_concurrent:
                continue

            # 计算能力匹配分数
            match_score = 0
            keywords = capability_keywords.get(caps.name, [])
            for kw in keywords:
                if kw in desc:
                    match_score += 1

            # 如果任务指定了 agent_id，直接匹配
            if subtask.assigned_agent and subtask.assigned_agent == aid:
                match_score = 100

            candidates.append((aid, match_score, active_tasks))

        if not candidates:
            return None

        # 排序：匹配分数降序，负载升序
        candidates.sort(key=lambda x: (-x[1], x[2]))
        return candidates[0][0]

    def _get_agent_active_tasks(self, agent_id: str) -> list[str]:
        """获取 Agent 当前活跃任务"""
        active = []
        for plan in self._active_plans.values():
            for st in plan.subtasks:
                if st.assigned_agent == agent_id and st.status in ("pending", "running"):
                    active.append(st.id)
        return active

    async def _execute_plan(self, plan: ExecutionPlan) -> list[dict]:
        """执行计划中的所有子任务"""
        results = []

        if plan.strategy == "parallel":
            # 并行执行所有无依赖的子任务
            tasks = []
            for subtask in plan.subtasks:
                if not subtask.dependencies:
                    tasks.append(self._execute_subtask(subtask))
            parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in parallel_results:
                if isinstance(r, Exception):
                    results.append({"success": False, "error": str(r)})
                else:
                    results.append(r)
        else:
            # 串行执行（或 DAG 简化为串行）
            completed_ids = set()
            for subtask in plan.subtasks:
                # 检查依赖
                if subtask.dependencies:
                    deps_met = all(d in completed_ids for d in subtask.dependencies)
                    if not deps_met:
                        results.append({
                            "success": False,
                            "subtask": subtask.name,
                            "error": "依赖未满足",
                        })
                        continue

                result = await self._execute_subtask(subtask)
                results.append(result)
                if result.get("success"):
                    completed_ids.add(subtask.id)

        return results

    async def _execute_subtask(self, subtask: SubTask) -> dict:
        """执行单个子任务"""
        subtask.status = "running"
        agent_id = subtask.assigned_agent

        if not agent_id or agent_id not in self._agents:
            subtask.status = "failed"
            return {
                "success": False,
                "subtask": subtask.name,
                "error": f"无可用 Agent: {agent_id}",
            }

        agent = self._agents[agent_id]
        logger.info(f"子任务 '{subtask.name}' 分配给 Agent '{agent.name}'")

        try:
            # 直接调用 Agent 执行
            result = await agent.execute_task({
                "task_id": subtask.id,
                "name": subtask.name,
                "description": subtask.description,
            })

            subtask.status = "completed" if result.success else "failed"
            subtask.result = result.output

            return {
                "success": result.success,
                "subtask": subtask.name,
                "agent": agent.name,
                "output": result.output,
                "tool_calls": result.tool_calls,
            }
        except Exception as e:
            subtask.status = "failed"
            return {
                "success": False,
                "subtask": subtask.name,
                "agent": agent.name,
                "error": str(e),
            }

    async def _aggregate(self, original_task: str, results: list[dict]) -> str:
        """聚合子任务结果"""
        if not self._llm:
            parts = []
            for r in results:
                status = "✅" if r.get("success") else "❌"
                name = r.get("subtask", "unknown")
                output = str(r.get("output", r.get("error", "")))[:300]
                parts.append(f"{status} {name}: {output}")
            return "\n\n".join(parts)

        from langchain_core.messages import SystemMessage, HumanMessage

        results_text = json.dumps(results, ensure_ascii=False, indent=2)
        system = "你是一个结果聚合专家。将多个子任务的执行结果合并为一个完整的最终报告。"
        response = self._llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=f"原始任务: {original_task}\n\n子任务结果:\n{results_text}"),
        ])
        return response.content or "执行完成"

    def get_plan_status(self, task_id: str) -> Optional[dict]:
        """获取计划执行状态"""
        plan = self._active_plans.get(task_id)
        if not plan:
            return None
        return {
            "task_id": task_id,
            "description": plan.description,
            "strategy": plan.strategy,
            "subtasks": [
                {
                    "id": st.id,
                    "name": st.name,
                    "assigned_agent": st.assigned_agent,
                    "status": st.status,
                }
                for st in plan.subtasks
            ],
        }

    def list_active_plans(self) -> list[dict]:
        """列出所有活跃计划"""
        return [
            self.get_plan_status(tid)
            for tid in self._active_plans
        ]


# 全局编排器实例
orchestrator = TaskOrchestrator()
