"""
测试固件
"""

import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.message_bus import MessageBus, AgentMessage, MessageType
from core.tool_registry import ToolRegistry, reset_tool_registry
from core.shared_context import SharedContext


@pytest.fixture
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def message_bus():
    """创建独立的 MessageBus 实例"""
    return MessageBus()


@pytest.fixture
def tool_registry(tmp_path):
    """创建独立的工具注册表"""
    reset_tool_registry()
    return ToolRegistry(str(tmp_path))


@pytest.fixture
def shared_context():
    """创建独立的共享上下文"""
    return SharedContext()
