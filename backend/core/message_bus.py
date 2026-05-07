"""
MessageBus - Agent 间实时消息通信

替代原来通过数据库轮询的 dispatch 机制。
基于 asyncio.Queue 实现，支持：
- 点对点消息
- 广播消息
- 请求-响应模式（带超时）
- 消息持久化（可选）
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Awaitable, Optional

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """消息类型"""
    TASK_REQUEST = "task_request"        # 任务请求
    TASK_RESULT = "task_result"          # 任务结果
    HELP_REQUEST = "help_request"        # 求助
    HELP_RESPONSE = "help_response"      # 求助响应
    CONTEXT_SHARE = "context_share"      # 共享上下文
    PROGRESS = "progress"                # 进度更新
    ERROR = "error"                      # 错误通知
    HEARTBEAT = "heartbeat"              # 心跳
    SYSTEM = "system"                    # 系统消息


@dataclass
class AgentMessage:
    """Agent 间通信消息"""
    type: MessageType
    from_agent: str                       # 发送方 Agent ID
    to_agent: Optional[str] = None        # 接收方 Agent ID（None = 广播）
    payload: dict = field(default_factory=dict)
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    reply_to: Optional[str] = None        # 关联的请求消息 ID

    def reply(self, payload: dict, msg_type: MessageType = MessageType.TASK_RESULT) -> "AgentMessage":
        """创建回复消息"""
        return AgentMessage(
            type=msg_type,
            from_agent=self.to_agent or "",
            to_agent=self.from_agent,
            payload=payload,
            correlation_id=self.correlation_id,
            reply_to=self.correlation_id,
        )


class MessageBus:
    """
    Agent 间消息总线
    
    每个 Agent 注册一个 inbox (asyncio.Queue)，
    通过 MessageBus 发送和接收消息。
    """

    def __init__(self):
        self._inboxes: dict[str, asyncio.Queue[AgentMessage]] = {}
        self._handlers: dict[str, list[Callable[[AgentMessage], Awaitable[None]]]] = {}
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._history: list[AgentMessage] = []
        self._max_history = 1000
        self._subscribers: dict[str, list[Callable[[AgentMessage], Awaitable[None]]]] = {}
        logger.info("MessageBus 初始化完成")

    def register(self, agent_id: str) -> asyncio.Queue[AgentMessage]:
        """注册 Agent，返回其 inbox"""
        if agent_id in self._inboxes:
            logger.warning(f"Agent {agent_id} 已注册，覆盖旧 inbox")
        inbox: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self._inboxes[agent_id] = inbox
        self._handlers[agent_id] = []
        logger.info(f"Agent {agent_id} 已注册到 MessageBus")
        return inbox

    def unregister(self, agent_id: str):
        """注销 Agent"""
        self._inboxes.pop(agent_id, None)
        self._handlers.pop(agent_id, None)
        # 取消等待中的请求
        for corr_id, future in list(self._pending_requests.items()):
            if not future.done():
                future.cancel()
        logger.info(f"Agent {agent_id} 已从 MessageBus 注销")

    def is_registered(self, agent_id: str) -> bool:
        """检查 Agent 是否已注册"""
        return agent_id in self._inboxes

    def get_registered_agents(self) -> list[str]:
        """获取所有已注册的 Agent ID"""
        return list(self._inboxes.keys())

    async def send(self, message: AgentMessage):
        """发送消息到指定 Agent"""
        target = message.to_agent
        if not target:
            logger.warning(f"消息没有指定接收方: {message.correlation_id}")
            return

        inbox = self._inboxes.get(target)
        if not inbox:
            logger.warning(f"目标 Agent {target} 未注册，消息丢弃: {message.correlation_id}")
            return

        self._record_history(message)
        await inbox.put(message)
        logger.debug(f"消息已发送: {message.from_agent} -> {target} [{message.type}]")

    async def broadcast(self, message: AgentMessage, exclude: Optional[str] = None):
        """广播消息到所有已注册的 Agent"""
        self._record_history(message)
        for agent_id, inbox in self._inboxes.items():
            if agent_id == exclude:
                continue
            msg_copy = AgentMessage(
                type=message.type,
                from_agent=message.from_agent,
                to_agent=agent_id,
                payload=message.payload.copy(),
                correlation_id=message.correlation_id,
                timestamp=message.timestamp,
                reply_to=message.reply_to,
            )
            await inbox.put(msg_copy)
        logger.debug(f"广播消息: {message.from_agent} -> all [{message.type}]")

    async def request(
        self, message: AgentMessage, timeout: float = 30.0
    ) -> AgentMessage:
        """
        请求-响应模式：发送消息并等待回复
        
        Args:
            message: 请求消息
            timeout: 超时秒数
            
        Returns:
            回复消息
            
        Raises:
            asyncio.TimeoutError: 超时
        """
        if not message.to_agent:
            raise ValueError("request 模式必须指定 to_agent")

        # 创建 Future 等待回复
        future: asyncio.Future[AgentMessage] = asyncio.get_event_loop().create_future()
        self._pending_requests[message.correlation_id] = future

        try:
            await self.send(message)
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                f"请求超时: {message.from_agent} -> {message.to_agent} "
                f"[{message.type}] corr={message.correlation_id}"
            )
            raise
        finally:
            self._pending_requests.pop(message.correlation_id, None)

    async def deliver_reply(self, message: AgentMessage):
        """投递回复消息（匹配等待中的 request）"""
        reply_to = message.reply_to
        if reply_to and reply_to in self._pending_requests:
            future = self._pending_requests[reply_to]
            if not future.done():
                future.set_result(message)
                return

        # 没有匹配的 request，走普通投递
        if message.to_agent:
            await self.send(message)

    def subscribe(self, pattern: str, handler: Callable[[AgentMessage], Awaitable[None]]):
        """
        订阅特定模式的消息（用于系统级监听）
        
        Args:
            pattern: 消息类型模式（如 "task_*" 或 "*" 表示全部）
            handler: 异步处理函数
        """
        if pattern not in self._subscribers:
            self._subscribers[pattern] = []
        self._subscribers[pattern].append(handler)
        logger.info(f"新增订阅: pattern={pattern}")

    async def notify_subscribers(self, message: AgentMessage):
        """通知订阅者"""
        for pattern, handlers in self._subscribers.items():
            if pattern == "*" or message.type.value.startswith(pattern.rstrip("*")):
                for handler in handlers:
                    try:
                        await handler(message)
                    except Exception as e:
                        logger.error(f"订阅者处理消息失败: {e}")

    def _record_history(self, message: AgentMessage):
        """记录消息历史"""
        self._history.append(message)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def get_history(
        self, agent_id: Optional[str] = None, limit: int = 50
    ) -> list[AgentMessage]:
        """获取消息历史"""
        if agent_id:
            msgs = [
                m for m in self._history
                if m.from_agent == agent_id or m.to_agent == agent_id
            ]
        else:
            msgs = self._history
        return msgs[-limit:]


# 全局 MessageBus 实例
message_bus = MessageBus()
