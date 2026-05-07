"""
Nix Core - 多智能体协作平台核心基础设施

提供：
- MessageBus: Agent间实时消息通信
- ToolRegistry: 共享工具注册表
- Agent: 有独立生命周期的智能体基类
- SharedContext: Agent间共享上下文
- TaskOrchestrator: 任务编排器
"""

from core.message_bus import MessageBus, AgentMessage
from core.tool_registry import ToolRegistry, Tool
from core.agent_base import Agent
from core.shared_context import SharedContext

__all__ = [
    "MessageBus",
    "AgentMessage", 
    "ToolRegistry",
    "Tool",
    "Agent",
    "SharedContext",
]
