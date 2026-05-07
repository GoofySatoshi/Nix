"""
MessageBus 测试
"""

import pytest
import asyncio
from core.message_bus import MessageBus, AgentMessage, MessageType


@pytest.mark.asyncio
async def test_register_and_unregister():
    """测试注册和注销"""
    bus = MessageBus()
    inbox = bus.register("agent-1")
    assert bus.is_registered("agent-1")
    assert "agent-1" in bus.get_registered_agents()

    bus.unregister("agent-1")
    assert not bus.is_registered("agent-1")
    assert "agent-1" not in bus.get_registered_agents()


@pytest.mark.asyncio
async def test_point_to_point_message():
    """测试点对点消息"""
    bus = MessageBus()
    inbox_a = bus.register("agent-a")
    inbox_b = bus.register("agent-b")

    msg = AgentMessage(
        type=MessageType.TASK_REQUEST,
        from_agent="agent-a",
        to_agent="agent-b",
        payload={"task": "do something"},
    )
    await bus.send(msg)

    received = await asyncio.wait_for(inbox_b.get(), timeout=1.0)
    assert received.type == MessageType.TASK_REQUEST
    assert received.from_agent == "agent-a"
    assert received.payload == {"task": "do something"}

    # agent-a 不应该收到
    assert inbox_a.empty()


@pytest.mark.asyncio
async def test_broadcast():
    """测试广播消息"""
    bus = MessageBus()
    inbox_a = bus.register("agent-a")
    inbox_b = bus.register("agent-b")
    inbox_c = bus.register("agent-c")

    msg = AgentMessage(
        type=MessageType.SYSTEM,
        from_agent="system",
        payload={"announcement": "hello all"},
    )
    await bus.broadcast(msg, exclude="agent-a")

    # agent-a 被排除
    assert inbox_a.empty()

    # agent-b 和 agent-c 应该收到
    received_b = await asyncio.wait_for(inbox_b.get(), timeout=1.0)
    assert received_b.to_agent == "agent-b"

    received_c = await asyncio.wait_for(inbox_c.get(), timeout=1.0)
    assert received_c.to_agent == "agent-c"


@pytest.mark.asyncio
async def test_request_response():
    """测试请求-响应模式"""
    bus = MessageBus()
    inbox_a = bus.register("agent-a")
    inbox_b = bus.register("agent-b")

    # agent-b 的响应处理
    async def respond_to_b():
        msg = await asyncio.wait_for(inbox_b.get(), timeout=2.0)
        reply = msg.reply({"answer": 42})
        await bus.deliver_reply(reply)

    # 先启动响应者
    task = asyncio.create_task(respond_to_b())

    # agent-a 发送请求
    request = AgentMessage(
        type=MessageType.TASK_REQUEST,
        from_agent="agent-a",
        to_agent="agent-b",
        payload={"question": "what is 6*7?"},
    )
    response = await bus.request(request, timeout=5.0)

    assert response.payload == {"answer": 42}
    await task


@pytest.mark.asyncio
async def test_request_timeout():
    """测试请求超时"""
    bus = MessageBus()
    bus.register("agent-a")
    bus.register("agent-b")  # 不会响应

    request = AgentMessage(
        type=MessageType.TASK_REQUEST,
        from_agent="agent-a",
        to_agent="agent-b",
        payload={"question": "hello?"},
    )

    with pytest.raises(asyncio.TimeoutError):
        await bus.request(request, timeout=0.1)


@pytest.mark.asyncio
async def test_message_history():
    """测试消息历史"""
    bus = MessageBus()
    bus.register("agent-a")
    bus.register("agent-b")

    for i in range(5):
        msg = AgentMessage(
            type=MessageType.TASK_REQUEST,
            from_agent="agent-a",
            to_agent="agent-b",
            payload={"i": i},
        )
        await bus.send(msg)

    history = bus.get_history(limit=3)
    assert len(history) == 3
    assert history[-1].payload["i"] == 4

    # 按 agent 过滤
    history_a = bus.get_history(agent_id="agent-a", limit=10)
    assert len(history_a) == 5


@pytest.mark.asyncio
async def test_reply_creates_correct_message():
    """测试 reply 方法创建正确的回复消息"""
    original = AgentMessage(
        type=MessageType.TASK_REQUEST,
        from_agent="agent-a",
        to_agent="agent-b",
        payload={"task": "test"},
        correlation_id="corr-123",
    )
    reply = original.reply({"result": "done"})
    assert reply.from_agent == "agent-b"
    assert reply.to_agent == "agent-a"
    assert reply.correlation_id == "corr-123"
    assert reply.reply_to == "corr-123"
