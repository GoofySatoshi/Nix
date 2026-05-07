"""
Agent - 有独立生命周期的智能体基类

替代原来的 AgentBase，提供：
- 独立生命周期（start/stop）
- 工具绑定
- 消息处理
- 子任务委派
- 进度报告
- 记忆
"""

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from core.message_bus import MessageBus, AgentMessage, MessageType, message_bus
from core.tool_registry import ToolRegistry, Tool, ToolCategory, get_tool_registry
from core.shared_context import SharedContext, shared_context

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Agent 状态"""
    IDLE = "idle"              # 空闲
    BUSY = "busy"              # 忙碌
    WAITING = "waiting"        # 等待外部输入
    STOPPED = "stopped"        # 已停止
    ERROR = "error"            # 错误


@dataclass
class AgentCapability:
    """Agent 能力声明"""
    name: str                  # 能力名称
    description: str           # 能力描述
    intent_tags: list[str]     # 能处理的意图标签
    tool_categories: list[ToolCategory]  # 需要的工具类别
    max_concurrent: int = 1    # 最大并发任务数


@dataclass
class AgentMemory:
    """Agent 个体记忆"""
    short_term: list[dict] = field(default_factory=list)  # 短期记忆（当前会话）
    long_term: dict = field(default_factory=dict)          # 长期记忆（持久化）
    max_short_term: int = 50

    def remember(self, event: dict):
        """记录短期记忆"""
        self.short_term.append({"timestamp": time.time(), **event})
        if len(self.short_term) > self.max_short_term:
            self.short_term = self.short_term[-self.max_short_term:]

    def get_recent(self, n: int = 10) -> list[dict]:
        """获取最近的 n 条记忆"""
        return self.short_term[-n:]

    def store_long_term(self, key: str, value: Any):
        """存储长期记忆"""
        self.long_term[key] = value

    def recall(self, key: str, default: Any = None) -> Any:
        """回忆长期记忆"""
        return self.long_term.get(key, default)


@dataclass
class TaskResult:
    """任务执行结果"""
    success: bool
    output: Any
    error: Optional[str] = None
    tool_calls: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class Agent(ABC):
    """
    智能体基类
    
    每个 Agent 有独立的生命周期，可以：
    - 接收和处理任务
    - 使用工具
    - 与其他 Agent 通信
    - 委派子任务
    - 维护记忆
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str = "",
        config: Optional[dict] = None,
        bus: Optional[MessageBus] = None,
        tools: Optional[ToolRegistry] = None,
        context: Optional[SharedContext] = None,
    ):
        self.id = agent_id
        self.name = name
        self.description = description
        self.config = config or {}
        self.status = AgentStatus.STOPPED

        # 基础设施（可注入，方便测试）
        self._bus = bus or message_bus
        self._tools = tools or get_tool_registry()
        self._context = context or shared_context
        self._memory = AgentMemory()

        # 运行时状态
        self._inbox: Optional[asyncio.Queue[AgentMessage]] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._current_tasks: dict[str, asyncio.Task] = {}

        # LLM 配置
        self._llm = None
        self._llm_config = self.config.get("llm", {})

    @property
    def capabilities(self) -> AgentCapability:
        """Agent 能力声明（子类必须实现）"""
        raise NotImplementedError

    @property
    def memory(self) -> AgentMemory:
        return self._memory

    # ---- 生命周期 ----

    async def start(self):
        """启动 Agent"""
        if self._running:
            logger.warning(f"Agent {self.name} 已在运行")
            return

        logger.info(f"Agent {self.name} 正在启动...")
        self.status = AgentStatus.IDLE
        self._running = True

        # 注册到 MessageBus
        self._inbox = self._bus.register(self.id)

        # 初始化 LLM
        await self._init_llm()

        # 启动消息处理循环
        self._task = asyncio.create_task(self._message_loop())

        # 更新共享上下文
        await self._context.update_agent_state(self.id, {
            "name": self.name,
            "status": self.status.value,
            "capabilities": self.capabilities.name if hasattr(self, 'capabilities') else "general",
        })

        logger.info(f"Agent {self.name} 已启动")

    async def stop(self):
        """停止 Agent"""
        if not self._running:
            return

        logger.info(f"Agent {self.name} 正在停止...")
        self._running = False
        self.status = AgentStatus.STOPPED

        # 取消当前任务
        for task_id, task in self._current_tasks.items():
            task.cancel()
        self._current_tasks.clear()

        # 取消消息循环
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # 注销
        self._bus.unregister(self.id)
        await self._context.remove_agent_state(self.id)

        logger.info(f"Agent {self.name} 已停止")

    # ---- 消息处理 ----

    async def _message_loop(self):
        """消息处理主循环"""
        logger.info(f"Agent {self.name} 消息循环已启动")
        while self._running:
            try:
                message = await asyncio.wait_for(self._inbox.get(), timeout=1.0)
                await self._handle_message(message)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Agent {self.name} 消息处理异常: {e}", exc_info=True)
        logger.info(f"Agent {self.name} 消息循环已结束")

    async def _handle_message(self, message: AgentMessage):
        """处理收到的消息"""
        logger.debug(f"Agent {self.name} 收到消息: {message.type} from {message.from_agent}")

        self._memory.remember({
            "type": "message_received",
            "from": message.from_agent,
            "msg_type": message.type,
        })

        try:
            if message.type == MessageType.TASK_REQUEST:
                await self._handle_task_request(message)
            elif message.type == MessageType.HELP_REQUEST:
                await self._handle_help_request(message)
            elif message.type == MessageType.CONTEXT_SHARE:
                await self._handle_context_share(message)
            elif message.type == MessageType.TASK_RESULT:
                await self._bus.deliver_reply(message)
            else:
                logger.debug(f"Agent {self.name} 忽略消息类型: {message.type}")
        except Exception as e:
            logger.error(f"Agent {self.name} 处理消息失败: {e}", exc_info=True)
            # 发送错误回复
            error_reply = message.reply(
                {"error": str(e)},
                msg_type=MessageType.ERROR,
            )
            await self._bus.send(error_reply)

    async def _handle_task_request(self, message: AgentMessage):
        """处理任务请求"""
        task_data = message.payload
        task_id = task_data.get("task_id", str(uuid.uuid4()))

        self.status = AgentStatus.BUSY
        await self._update_status()

        try:
            # 在共享上下文中创建任务
            await self._context.create_task_context(
                task_id, task_data.get("description", ""), self.id
            )

            # 执行任务
            result = await self.execute_task(task_data)

            # 发送结果
            reply = message.reply({
                "task_id": task_id,
                "success": result.success,
                "output": result.output,
                "error": result.error,
                "tool_calls": result.tool_calls,
            })
            await self._bus.send(reply)

            # 记忆
            self._memory.remember({
                "type": "task_completed",
                "task_id": task_id,
                "success": result.success,
            })

        except Exception as e:
            error_reply = message.reply(
                {"task_id": task_id, "success": False, "error": str(e)},
                msg_type=MessageType.ERROR,
            )
            await self._bus.send(error_reply)
        finally:
            self.status = AgentStatus.IDLE
            await self._update_status()

    async def _handle_help_request(self, message: AgentMessage):
        """处理求助消息"""
        # 默认实现：评估自己能否帮忙，如果能就处理
        can_help = await self._evaluate_help(message.payload)
        if can_help:
            result = await self.handle_help(message.payload)
            reply = message.reply({"help_result": result})
            await self._bus.send(reply)
        else:
            reply = message.reply({"declined": True, "reason": "不在能力范围内"})
            await self._bus.send(reply)

    async def _handle_context_share(self, message: AgentMessage):
        """处理上下文共享"""
        key = message.payload.get("key")
        value = message.payload.get("value")
        if key:
            await self._context.set_global(f"shared:{key}", value)
            self._memory.remember({"type": "context_received", "key": key})

    # ---- 任务执行（子类实现）----

    @abstractmethod
    async def execute_task(self, task_data: dict) -> TaskResult:
        """
        执行任务（子类必须实现）
        
        Args:
            task_data: 任务数据，包含 id, name, description 等
            
        Returns:
            TaskResult
        """
        ...

    async def handle_help(self, request: dict) -> Any:
        """处理求助（子类可覆盖）"""
        return "我暂时无法处理这个请求"

    async def _evaluate_help(self, request: dict) -> bool:
        """评估是否能帮忙（子类可覆盖）"""
        return False

    # ---- 工具使用 ----

    def get_tools(self, categories: Optional[list[ToolCategory]] = None) -> list[Tool]:
        """获取可用工具"""
        if categories:
            tools = []
            for cat in categories:
                tools.extend(self._tools.list_tools(cat))
            return tools
        return self._tools.list_tools()

    def use_tool(self, tool_name: str, **kwargs) -> str:
        """使用工具"""
        tool = self._tools.get(tool_name)
        if not tool:
            return f"工具 {tool_name} 不存在"
        try:
            return tool.func(**kwargs)
        except Exception as e:
            return f"工具执行错误: {e}"

    # ---- 子任务委派 ----

    async def delegate(
        self,
        target_agent: str,
        task_name: str,
        task_description: str,
        timeout: float = 60.0,
        **kwargs,
    ) -> dict:
        """
        委派子任务给其他 Agent
        
        Args:
            target_agent: 目标 Agent ID
            task_name: 任务名称
            task_description: 任务描述
            timeout: 超时秒数
            
        Returns:
            任务结果
        """
        logger.info(f"Agent {self.name} 委派任务给 {target_agent}: {task_name}")

        # 报告进度
        await self.report_progress(0, f"正在委派任务给 {target_agent}...")

        message = AgentMessage(
            type=MessageType.TASK_REQUEST,
            from_agent=self.id,
            to_agent=target_agent,
            payload={
                "task_id": str(uuid.uuid4()),
                "name": task_name,
                "description": task_description,
                "delegated_by": self.id,
                **kwargs,
            },
        )

        try:
            result = await self._bus.request(message, timeout=timeout)
            self._memory.remember({
                "type": "delegation_success",
                "target": target_agent,
                "task": task_name,
            })
            return result.payload
        except asyncio.TimeoutError:
            self._memory.remember({
                "type": "delegation_timeout",
                "target": target_agent,
                "task": task_name,
            })
            return {"success": False, "error": f"Agent {target_agent} 响应超时"}

    async def broadcast_help(self, request: dict, timeout: float = 30.0) -> list[dict]:
        """向所有 Agent 广播求助"""
        message = AgentMessage(
            type=MessageType.HELP_REQUEST,
            from_agent=self.id,
            payload=request,
        )
        # 收集响应
        responses = []
        for agent_id in self._bus.get_registered_agents():
            if agent_id == self.id:
                continue
            try:
                msg = AgentMessage(
                    type=MessageType.HELP_REQUEST,
                    from_agent=self.id,
                    to_agent=agent_id,
                    payload=request,
                )
                resp = await self._bus.request(msg, timeout=timeout)
                if not resp.payload.get("declined"):
                    responses.append(resp.payload)
            except asyncio.TimeoutError:
                continue
        return responses

    # ---- 进度报告 ----

    async def report_progress(self, progress: int, message: str, task_id: str = ""):
        """报告任务进度"""
        await self._context.update_agent_state(self.id, {
            "name": self.name,
            "status": self.status.value,
            "progress": progress,
            "progress_message": message,
        })

        # 广播进度
        progress_msg = AgentMessage(
            type=MessageType.PROGRESS,
            from_agent=self.id,
            payload={
                "task_id": task_id,
                "progress": progress,
                "message": message,
            },
        )
        await self._bus.broadcast(progress_msg, exclude=self.id)

    # ---- LLM ----

    async def _init_llm(self):
        """初始化 LLM"""
        llm_config = self._llm_config
        if not llm_config:
            return

        try:
            from langchain_openai import ChatOpenAI
            kwargs = {
                "api_key": llm_config.get("api_key", ""),
                "model": llm_config.get("model", "gpt-3.5-turbo"),
                "temperature": llm_config.get("temperature", 0.7),
                "max_tokens": llm_config.get("max_tokens", 4096),
                "timeout": llm_config.get("timeout", 300),
            }
            if llm_config.get("base_url"):
                kwargs["base_url"] = llm_config["base_url"]
            self._llm = ChatOpenAI(**kwargs)
            logger.info(f"Agent {self.name} LLM 初始化完成")
        except Exception as e:
            logger.warning(f"Agent {self.name} LLM 初始化失败: {e}")

    async def llm_invoke(self, messages: list) -> str:
        """调用 LLM"""
        if not self._llm:
            raise RuntimeError("LLM 未初始化")
        response = self._llm.invoke(messages)
        return response.content or ""

    # ---- 状态 ----

    async def _update_status(self):
        """更新共享上下文中的状态"""
        await self._context.update_agent_state(self.id, {
            "name": self.name,
            "status": self.status.value,
        })

    def get_info(self) -> dict:
        """获取 Agent 信息"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "capabilities": self.capabilities.name if hasattr(self, 'capabilities') else "general",
            "memory_size": len(self._memory.short_term),
        }
