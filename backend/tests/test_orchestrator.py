"""
TaskOrchestrator 测试
"""

import pytest
import asyncio
from core.message_bus import MessageBus
from core.tool_registry import ToolRegistry
from core.shared_context import SharedContext
from core.agent_base import Agent, AgentCapability, TaskResult
from core.orchestrator import TaskOrchestrator


class SimpleAgent(Agent):
    """简单测试 Agent"""
    def __init__(self, result_text="done", **kwargs):
        super().__init__(**kwargs)
        self._result_text = result_text
        self.execution_count = 0

    @property
    def capabilities(self):
        return AgentCapability(
            name="simple",
            description="简单测试",
            intent_tags=["test"],
            tool_categories=[],
        )

    async def execute_task(self, task_data):
        self.execution_count += 1
        return TaskResult(success=True, output=self._result_text)


@pytest.fixture
def setup(tmp_path):
    bus = MessageBus()
    tools = ToolRegistry(str(tmp_path))
    context = SharedContext()
    return bus, tools, context


@pytest.mark.asyncio
async def test_orchestrator_single_task(setup, tmp_path):
    """测试单任务执行"""
    bus, tools, context = setup

    agent = SimpleAgent(
        agent_id="a1", name="Agent1",
        result_text="任务完成",
        bus=bus, tools=tools, context=context,
    )
    await agent.start()

    orch = TaskOrchestrator(bus=bus, context=context)
    orch.register_agent(agent)

    result = await orch.execute("测试任务")
    assert result["success"] is True
    assert "任务完成" in str(result["output"])
    assert "a1" in result["agents_used"]

    await agent.stop()


@pytest.mark.asyncio
async def test_orchestrator_multiple_agents(setup, tmp_path):
    """测试多 Agent 分配"""
    bus, tools, context = setup

    agent1 = SimpleAgent(
        agent_id="a1", name="Agent1",
        bus=bus, tools=tools, context=context,
    )
    agent2 = SimpleAgent(
        agent_id="a2", name="Agent2",
        bus=bus, tools=tools, context=context,
    )
    await agent1.start()
    await agent2.start()

    orch = TaskOrchestrator(bus=bus, context=context)
    orch.register_agent(agent1)
    orch.register_agent(agent2)

    result = await orch.execute("测试任务")
    assert result["success"] is True
    assert len(result["agents_used"]) >= 1

    await agent1.stop()
    await agent2.stop()


@pytest.mark.asyncio
async def test_orchestrator_plan_status(setup, tmp_path):
    """测试计划状态查询"""
    bus, tools, context = setup

    agent = SimpleAgent(
        agent_id="a1", name="Agent1",
        bus=bus, tools=tools, context=context,
    )
    await agent.start()

    orch = TaskOrchestrator(bus=bus, context=context)
    orch.register_agent(agent)

    # 启动一个任务（不等完成）
    task = asyncio.create_task(orch.execute("测试任务"))
    await asyncio.sleep(0.1)

    plans = orch.list_active_plans()
    # 计划可能已经完成（简单任务很快）
    assert isinstance(plans, list)

    await task
    await agent.stop()


@pytest.mark.asyncio
async def test_orchestrator_no_agents():
    """测试无可用 Agent"""
    orch = TaskOrchestrator()
    result = await orch.execute("测试任务")
    # 应该有某种错误处理
    assert isinstance(result, dict)
