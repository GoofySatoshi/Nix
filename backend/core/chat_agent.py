"""
ChatAgent - 对话型智能体

专注于自然语言对话、代码分析、信息查询。
使用意图识别来路由到合适的处理逻辑。
"""

import json
import logging
import re
from typing import Optional

from core.agent_base import Agent, AgentCapability, TaskResult
from core.tool_registry import ToolCategory

logger = logging.getLogger(__name__)


class ChatAgent(Agent):
    """对话型智能体"""

    def __init__(self, agent_id: str, name: str = "ChatAgent", **kwargs):
        super().__init__(agent_id=agent_id, name=name, description="对话与代码分析智能体", **kwargs)
        self._intent_cache: dict[str, str] = {}

    @property
    def capabilities(self) -> AgentCapability:
        return AgentCapability(
            name="chat",
            description="自然语言对话、代码分析、信息查询",
            intent_tags=["general_chat", "information_query", "code_analysis", "code_review"],
            tool_categories=[ToolCategory.FILE, ToolCategory.SEARCH],
            max_concurrent=3,
        )

    async def execute_task(self, task_data: dict) -> TaskResult:
        """执行对话任务"""
        description = task_data.get("description", "")
        task_id = task_data.get("task_id", "unknown")

        await self.report_progress(10, "正在分析意图...", task_id)

        # 意图识别
        intent = await self._classify_intent(description)
        logger.info(f"ChatAgent 识别意图: {intent}")

        await self.report_progress(30, f"意图: {intent}，正在处理...", task_id)

        # 根据意图路由
        if intent in ("general_chat", "information_query"):
            result = await self._handle_chat(description)
        elif intent in ("code_analysis", "code_review"):
            result = await self._handle_code_analysis(description, task_id)
        else:
            result = await self._handle_chat(description)

        await self.report_progress(100, "完成", task_id)

        return TaskResult(
            success=True,
            output=result,
            metadata={"intent": intent},
        )

    async def _classify_intent(self, message: str) -> str:
        """意图识别"""
        if not self._llm:
            return self._keyword_intent(message)

        prompt = """你是一个意图分类器。根据用户消息判断意图类别，只返回类别名称。

类别：
- general_chat: 纯闲聊问候
- information_query: 知识问答
- code_analysis: 分析/解释已有代码
- code_review: 代码质量审查

只返回类别名称。"""

        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            response = self._llm.invoke([
                SystemMessage(content=prompt),
                HumanMessage(content=f"用户消息: {message}")
            ])
            result = (response.content or "").strip().lower()
            valid = {"general_chat", "information_query", "code_analysis", "code_review"}
            return result if result in valid else "general_chat"
        except Exception as e:
            logger.warning(f"意图识别失败: {e}")
            return self._keyword_intent(message)

    def _keyword_intent(self, message: str) -> str:
        """关键词兜底意图识别"""
        code_kw = ["代码", "分析", "解释", "review", "审查", "看下", "看看"]
        if any(kw in message for kw in code_kw):
            return "code_analysis"
        return "general_chat"

    async def _handle_chat(self, message: str) -> str:
        """处理普通对话"""
        if not self._llm:
            return f"[ChatAgent] 收到消息: {message}\n（LLM 未配置，无法生成回复）"

        from langchain_core.messages import SystemMessage, HumanMessage
        system = "你是一个智能助手，善于回答问题和进行对话。回答简洁明了。"
        response = self._llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=message),
        ])
        return response.content or ""

    async def _handle_code_analysis(self, message: str, task_id: str) -> str:
        """处理代码分析"""
        # 尝试从消息中提取文件路径
        file_paths = re.findall(r'[\w/\\]+\.\w+', message)

        file_contents = []
        for fp in file_paths[:5]:  # 最多读5个文件
            content = self.use_tool("file_read", path=fp)
            if not content.startswith("读取错误"):
                file_contents.append(f"=== {fp} ===\n{content}")

        if not self._llm:
            return f"[代码分析] 找到文件: {file_paths}\n（LLM 未配置）"

        from langchain_core.messages import SystemMessage, HumanMessage
        context = "\n\n".join(file_contents) if file_contents else "未找到相关文件"
        system = "你是一个代码分析专家。根据提供的代码给出详细的分析和解释。"
        response = self._llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=f"用户请求: {message}\n\n代码上下文:\n{context}"),
        ])
        return response.content or ""

    async def handle_help(self, request: dict) -> str:
        """处理其他 Agent 的求助"""
        question = request.get("question", request.get("description", ""))
        if self._llm:
            from langchain_core.messages import HumanMessage
            response = self._llm.invoke([HumanMessage(content=f"请简要回答: {question}")])
            return response.content or ""
        return f"[ChatAgent] 无法回答: {question}（LLM 未配置）"

    async def _evaluate_help(self, request: dict) -> bool:
        """评估能否帮忙"""
        intent = request.get("intent", "")
        return intent in ("general_chat", "information_query", "code_analysis")
