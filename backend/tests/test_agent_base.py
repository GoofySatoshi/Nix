"""
Agent 基类测试
"""

import pytest
import asyncio
from core.agent_base import Agent, AgentCapability, AgentStatus, TaskResult
from core.message_bus import MessageBus, AgentMessage, MessageType
from core.tool_registry import ToolRegistry, ToolCategory
from core.shared_context import SharedContext


class MockAgent(Agent):
    """用于测试的 Mock Agent"""

    @property
    def capabilities(self):
        return AgentCapability(
            name="mock",
            description="测试用 Agent",
            intent_tags=["test"],
            tool_categories=[ToolCategory.FILE],
        )

    async def execute_task(self, task_data):
        return TaskResult(success=True, output=f"完成: {task_data.get('description', '')}")


@pytest.fixture
def setup():
    """创建测试环境"""
    bus = MessageBus()
    context = SharedContext()
    return bus, context


@pytest.mark.asyncio
async def test_agent_lifecycle(setup, tmp_path):
    """测试 Agent 生命周期"""
    bus, context = setup
    tools = ToolRegistry(str(tmp_path))

    agent = MockAgent(
        agent_id="test-1",
        name="TestAgent",
        bus=bus,
        tools=tools,
        context=context,
    )

    assert agent.status == AgentStatus.STOPPED

    await agent.start()
    assert agent.status == AgentStatus.IDLE
    assert bus.is_registered("test-1")

    await agent.stop()
    assert agent.status == AgentStatus.STOPPED
    assert not bus.is_registered("test-1")


@pytest.mark.asyncio
async def test_agent_handles_task_request(setup, tmp_path):
    """测试 Agent 处理任务请求"""
    bus, context = setup
    tools = ToolRegistry(str(tmp_path))

    agent = MockAgent(
        agent_id="test-1",
        name="TestAgent",
        bus=bus,
        tools=tools,
        context=context,
    )
    await agent.start()

    # 注册另一个 inbox 来接收回复
    reply_inbox = bus.register("sender")

    # 发送任务请求
    request = AgentMessage(
        type=MessageType.TASK_REQUEST,
        from_agent="sender",
        to_agent="test-1",
        payload={"task_id": "t1", "description": "做点什么"},
    )
    await bus.send(request)

    # 等待处理
    await asyncio.sleep(0.5)

    # 检查回复
    reply = await asyncio.wait_for(reply_inbox.get(), timeout=2.0)
    assert reply.type == MessageType.TASK_RESULT
    assert reply.payload["success"] is True
    assert "完成" in reply.payload["output"]

    await agent.stop()


@pytest.mark.asyncio
async def test_agent_info(setup, tmp_path):
    """测试 Agent 信息获取"""
    bus, context = setup
    tools = ToolRegistry(str(tmp_path))

    agent = MockAgent(
        agent_id="test-1",
        name="TestAgent",
        description="测试Agent",
        bus=bus,
        tools=tools,
        context=context,
    )

    info = agent.get_info()
    assert info["id"] == "test-1"
    assert info["name"] == "TestAgent"
    assert info["description"] == "测试Agent"
    assert info["status"] == "stopped"


@pytest.mark.asyncio
async def test_agent_memory(setup, tmp_path):
    """测试 Agent 记忆系统"""
    bus, context = setup
    tools = ToolRegistry(str(tmp_path))

    agent = MockAgent(
        agent_id="test-1",
        name="TestAgent",
        bus=bus,
        tools=tools,
        context=context,
    )

    # 短期记忆
    agent.memory.remember({"type": "test", "data": "hello"})
    recent = agent.memory.get_recent(1)
    assert len(recent) == 1
    assert recent[0]["data"] == "hello"

    # 长期记忆
    agent.memory.store_long_term("key", "value")
    assert agent.memory.recall("key") == "value"
    assert agent.memory.recall("nonexistent", "default") == "default"


@pytest.mark.asyncio
async def test_agent_use_tool(setup, tmp_path):
    """测试 Agent 使用工具"""
    bus, context = setup
    tools = ToolRegistry(str(tmp_path))

    # 创建测试文件
    (tmp_path / "test.txt").write_text("hello")

    agent = MockAgent(
        agent_id="test-1",
        name="TestAgent",
        bus=bus,
        tools=tools,
        context=context,
    )

    # 使用工具
    content = agent.use_tool("file_read", path="test.txt")
    assert content == "hello"

    # 不存在的工具
    result = agent.use_tool("nonexistent_tool")
    assert "不存在" in result
