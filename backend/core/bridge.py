"""
Core Bridge - 连接新核心与现有 FastAPI 应用

提供初始化函数和兼容层，让现有路由可以逐步迁移到新架构。
"""

import logging
import os
from typing import Optional

from core.message_bus import MessageBus, message_bus
from core.tool_registry import ToolRegistry, get_tool_registry
from core.shared_context import SharedContext, shared_context
from core.orchestrator import TaskOrchestrator, orchestrator
from core.chat_agent import ChatAgent
from core.code_agent import CodeAgent

logger = logging.getLogger(__name__)


# Agent 实例缓存（新架构）
_core_agents: dict[str, any] = {}


async def initialize_core(workspace_root: str = ".", llm_config: Optional[dict] = None):
    """
    初始化核心基础设施
    
    在 FastAPI 启动时调用。
    """
    logger.info("正在初始化核心基础设施...")

    # 1. 初始化工具注册表
    tools = get_tool_registry(workspace_root)

    # 2. 创建默认 Agent
    chat_agent = ChatAgent(
        agent_id="chat-default",
        name="对话助手",
        tools=tools,
        bus=message_bus,
        context=shared_context,
        config={"llm": llm_config} if llm_config else {},
    )

    code_agent = CodeAgent(
        agent_id="code-default",
        name="开发助手",
        tools=tools,
        bus=message_bus,
        context=shared_context,
        config={"llm": llm_config} if llm_config else {},
    )

    # 3. 启动 Agent
    await chat_agent.start()
    await code_agent.start()

    # 4. 注册到编排器
    orchestrator.register_agent(chat_agent)
    orchestrator.register_agent(code_agent)

    # 5. 缓存
    _core_agents["chat-default"] = chat_agent
    _core_agents["code-default"] = code_agent

    if llm_config:
        try:
            from langchain_openai import ChatOpenAI
            kwargs = {"api_key": llm_config["api_key"], "model": llm_config.get("model", "gpt-3.5-turbo")}
            if llm_config.get("base_url"):
                kwargs["base_url"] = llm_config["base_url"]
            orchestrator.set_llm(ChatOpenAI(**kwargs))
        except Exception as e:
            logger.warning(f"编排器 LLM 初始化失败: {e}")

    logger.info(f"核心基础设施初始化完成, {len(_core_agents)} 个 Agent 已启动")


async def shutdown_core():
    """关闭核心基础设施"""
    logger.info("正在关闭核心基础设施...")
    for agent_id, agent in _core_agents.items():
        try:
            await agent.stop()
        except Exception as e:
            logger.error(f"停止 Agent {agent_id} 失败: {e}")
    _core_agents.clear()
    logger.info("核心基础设施已关闭")


def get_core_agents() -> dict:
    """获取所有核心 Agent"""
    return dict(_core_agents)


def get_core_agent(agent_id: str):
    """获取指定 Agent"""
    return _core_agents.get(agent_id)


async def update_workspace(workspace_root: str):
    """更新工作目录"""
    tools = get_tool_registry()
    tools.set_workspace(workspace_root)
    logger.info(f"工作目录已更新: {workspace_root}")
