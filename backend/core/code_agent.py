"""
CodeAgent - 代码开发型智能体

专注于代码生成、文件操作、终端命令执行。
能够处理复合型开发任务，支持多步骤执行。
"""

import json
import logging
import os
import re
from typing import Optional

from core.agent_base import Agent, AgentCapability, TaskResult
from core.tool_registry import ToolCategory

logger = logging.getLogger(__name__)


class CodeAgent(Agent):
    """代码开发型智能体"""

    def __init__(self, agent_id: str, name: str = "CodeAgent", **kwargs):
        super().__init__(agent_id=agent_id, name=name, description="代码开发与文件操作智能体", **kwargs)

    @property
    def capabilities(self) -> AgentCapability:
        return AgentCapability(
            name="developer",
            description="代码生成、文件操作、终端命令、项目开发",
            intent_tags=[
                "file_operation", "code_generation", "terminal_command",
                "project_task", "project_analysis",
            ],
            tool_categories=[
                ToolCategory.FILE, ToolCategory.TERMINAL,
                ToolCategory.SEARCH, ToolCategory.SKILL,
            ],
            max_concurrent=2,
        )

    async def execute_task(self, task_data: dict) -> TaskResult:
        """执行开发任务"""
        description = task_data.get("description", "")
        task_id = task_data.get("task_id", "unknown")
        tool_calls = []

        await self.report_progress(5, "正在规划执行步骤...", task_id)

        # 生成执行计划
        plan = await self._generate_plan(description, task_id)

        if not plan:
            return TaskResult(success=False, output="", error="无法生成执行计划")

        total_steps = len(plan)
        results = []

        for i, step in enumerate(plan):
            progress = int(10 + (80 * (i / total_steps)))
            step_name = step.get("name", f"步骤{i+1}")
            await self.report_progress(progress, f"[{i+1}/{total_steps}] {step_name}", task_id)

            try:
                step_result = await self._execute_step(step)
                results.append({"step": step_name, "success": True, "result": step_result})
                tool_calls.append({
                    "step": step_name,
                    "tool": step.get("tool", "unknown"),
                    "success": True,
                })
            except Exception as e:
                logger.error(f"步骤 {step_name} 失败: {e}")
                results.append({"step": step_name, "success": False, "error": str(e)})
                tool_calls.append({
                    "step": step_name,
                    "tool": step.get("tool", "unknown"),
                    "success": False,
                    "error": str(e),
                })
                # 非关键步骤失败继续，关键步骤失败停止
                if step.get("critical", False):
                    break

        await self.report_progress(95, "正在总结结果...", task_id)

        # 总结结果
        summary = await self._summarize_results(description, results, task_id)

        await self.report_progress(100, "完成", task_id)

        all_success = all(r.get("success") for r in results)
        return TaskResult(
            success=all_success,
            output=summary,
            tool_calls=tool_calls,
            metadata={"steps_total": total_steps, "steps_completed": len(results)},
        )

    async def _generate_plan(self, description: str, task_id: str) -> list[dict]:
        """生成执行计划"""
        if not self._llm:
            # 无 LLM 时的简单计划
            return [{"name": "执行任务", "tool": "file_read", "params": {"path": "."}}]

        # 获取项目上下文
        project_context = self._get_project_context()

        tool_names = [t.name for t in self.get_tools()]

        system = f"""你是一个任务规划工程师。将用户需求拆解为可直接执行的步骤。

## 项目上下文
{project_context}

## 可用工具
{', '.join(tool_names)}

## 规则
1. 每步对应一个工具操作
2. description 必须包含具体文件路径和内容
3. 步骤数：简单2-3步，中等4-6步，复杂6-10步
4. name 不超过8字，动词开头

## 输出格式
严格 JSON 数组：
[{{"name": "步骤名", "tool": "工具名", "params": {{...}}, "critical": false}}]

不要其他文字。"""

        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            response = self._llm.invoke([
                SystemMessage(content=system),
                HumanMessage(content=description),
            ])
            content = response.content.strip()

            # 提取 JSON
            json_match = re.search(r'```(?:json)?\s*(.*?)```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1).strip()
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)

            plan = json.loads(content)
            if isinstance(plan, list) and len(plan) > 0:
                return plan
        except Exception as e:
            logger.warning(f"计划生成失败: {e}")

        return [{"name": "执行任务", "tool": "file_read", "params": {"path": "."}}]

    async def _execute_step(self, step: dict) -> str:
        """执行单个步骤"""
        tool_name = step.get("tool")
        params = step.get("params", {})

        if not tool_name:
            return "无工具指定"

        # 特殊处理：如果是写文件类操作，先确保目录存在
        if tool_name in ("file_create", "file_update"):
            path = params.get("path", "")
            if path:
                full_path = os.path.join(self._tools.workspace_root, path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)

        result = self.use_tool(tool_name, **params)
        self._memory.remember({
            "type": "tool_call",
            "tool": tool_name,
            "params": params,
            "result_preview": str(result)[:200],
        })
        return result

    def _get_project_context(self) -> str:
        """获取项目上下文信息"""
        workspace = self._tools.workspace_root
        if not os.path.isdir(workspace):
            return "无项目上下文"

        lines = []
        try:
            for item in sorted(os.listdir(workspace)):
                if item.startswith('.') or item in ('node_modules', 'venv', '__pycache__', 'build', 'dist'):
                    continue
                item_path = os.path.join(workspace, item)
                if os.path.isdir(item_path):
                    lines.append(f"  {item}/")
                    try:
                        for sub in sorted(os.listdir(item_path))[:8]:
                            if sub.startswith('.'):
                                continue
                            lines.append(f"    {sub}")
                    except PermissionError:
                        pass
                else:
                    lines.append(f"  {item}")
        except Exception:
            pass

        return "\n".join(lines[:60]) if lines else "空目录"

    async def _summarize_results(
        self, original_task: str, results: list[dict], task_id: str
    ) -> str:
        """总结执行结果"""
        if not self._llm:
            # 无 LLM 时简单拼接
            parts = []
            for r in results:
                status = "✅" if r.get("success") else "❌"
                parts.append(f"{status} {r['step']}: {str(r.get('result', r.get('error', '')))[:200]}")
            return "\n".join(parts)

        from langchain_core.messages import SystemMessage, HumanMessage

        results_text = json.dumps(results, ensure_ascii=False, indent=2)
        system = "你是一个执行结果总结器。根据任务和执行结果，给出简洁的完成报告。"
        response = self._llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=f"原始任务: {original_task}\n\n执行结果:\n{results_text}"),
        ])
        return response.content or "执行完成"

    async def handle_help(self, request: dict) -> str:
        """处理其他 Agent 的求助（文件操作相关）"""
        action = request.get("action")
        if action == "read_file":
            path = request.get("path", "")
            return self.use_tool("file_read", path=path)
        elif action == "search":
            query = request.get("query", "")
            return self.use_tool("file_search", query=query)
        return "无法处理该求助"

    async def _evaluate_help(self, request: dict) -> bool:
        """评估能否帮忙"""
        action = request.get("action", "")
        return action in ("read_file", "search", "write_file", "execute")
