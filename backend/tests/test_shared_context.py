"""
SharedContext 测试
"""

import pytest
import asyncio
from core.shared_context import SharedContext


@pytest.mark.asyncio
async def test_task_context_lifecycle():
    """测试任务上下文生命周期"""
    ctx = SharedContext()

    # 创建
    task = await ctx.create_task_context("t1", "测试任务", "agent-1")
    assert task.task_id == "t1"
    assert task.description == "测试任务"
    assert task.assigned_agent == "agent-1"

    # 获取
    retrieved = await ctx.get_task_context("t1")
    assert retrieved is not None
    assert retrieved.task_id == "t1"

    # 更新状态
    await ctx.update_task_status("t1", "running")
    assert (await ctx.get_task_context("t1")).status == "running"

    # 设置共享数据
    await ctx.set_task_data("t1", "key1", "value1")
    assert await ctx.get_task_data("t1", "key1") == "value1"

    # 添加子任务结果
    await ctx.add_subtask_result("t1", "sub-1", {"output": "done"})
    results = await ctx.get_task_results("t1")
    assert "sub-1" in results

    # 清理
    await ctx.cleanup_task("t1")
    assert await ctx.get_task_context("t1") is None


@pytest.mark.asyncio
async def test_agent_state():
    """测试 Agent 状态管理"""
    ctx = SharedContext()

    await ctx.update_agent_state("agent-1", {"name": "TestAgent", "status": "idle"})
    state = await ctx.get_agent_state("agent-1")
    assert state["name"] == "TestAgent"
    assert "updated_at" in state

    all_states = await ctx.get_all_agent_states()
    assert "agent-1" in all_states

    await ctx.remove_agent_state("agent-1")
    assert await ctx.get_agent_state("agent-1") == {}


@pytest.mark.asyncio
async def test_global_data():
    """测试全局共享数据"""
    ctx = SharedContext()

    await ctx.set_global("config", {"debug": True})
    assert await ctx.get_global("config") == {"debug": True}
    assert await ctx.get_global("nonexistent", "default") == "default"


@pytest.mark.asyncio
async def test_project_info():
    """测试项目信息"""
    ctx = SharedContext()

    info = {"name": "Nix", "version": "1.0"}
    await ctx.set_project_info(info)
    assert await ctx.get_project_info() == info


@pytest.mark.asyncio
async def test_snapshot():
    """测试上下文快照"""
    ctx = SharedContext()

    await ctx.create_task_context("t1", "任务1")
    await ctx.update_agent_state("a1", {"name": "Agent1"})
    await ctx.set_global("key", "value")
    await ctx.set_project_info({"name": "test"})

    snapshot = await ctx.snapshot()
    assert "t1" in snapshot["tasks"]
    assert "a1" in snapshot["agents"]
    assert "key" in snapshot["global_keys"]
    assert snapshot["project_info"]["name"] == "test"


@pytest.mark.asyncio
async def test_get_nonexistent_returns_default():
    """测试获取不存在的数据返回默认值"""
    ctx = SharedContext()
    assert await ctx.get_task_context("nonexistent") is None
    assert await ctx.get_task_data("nonexistent", "key", "default") == "default"
    assert await ctx.get_global("nonexistent") is None
