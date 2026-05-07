"""
ToolRegistry - 共享工具注册表

所有 Agent 共享同一套工具，通过注册表统一管理。
替代原来在 chat_agent.py 里硬编码的工具创建逻辑。
"""

import json
import logging
import os
import re
import fnmatch
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ToolCategory(str, Enum):
    """工具类别"""
    FILE = "file"
    TERMINAL = "terminal"
    BROWSER = "browser"
    DATABASE = "database"
    SKILL = "skill"
    SEARCH = "search"
    SYSTEM = "system"


@dataclass
class Tool:
    """工具定义"""
    name: str
    description: str
    category: ToolCategory
    func: Callable
    parameters: dict  # JSON Schema 格式的参数定义
    dangerous: bool = False       # 是否为危险操作
    requires_confirm: bool = False # 是否需要用户确认

    def to_langchain(self):
        """转换为 LangChain StructuredTool"""
        try:
            from langchain_core.tools import StructuredTool
            return StructuredTool.from_function(
                func=self.func,
                name=self.name,
                description=self.description,
            )
        except ImportError:
            return None


class ToolRegistry:
    """
    共享工具注册表
    
    所有 Agent 共享同一套工具实例。
    Agent 可以根据自己的能力选择使用工具的子集。
    """

    def __init__(self, workspace_root: str = "."):
        self._tools: dict[str, Tool] = {}
        self._workspace_root = os.path.abspath(workspace_root)
        self._register_builtins()
        logger.info(f"ToolRegistry 初始化完成, workspace={self._workspace_root}")

    @property
    def workspace_root(self) -> str:
        return self._workspace_root

    def set_workspace(self, path: str):
        """更新工作目录"""
        self._workspace_root = os.path.abspath(path)
        logger.info(f"工作目录已更新: {self._workspace_root}")

    def register(self, tool: Tool):
        """注册工具"""
        self._tools[tool.name] = tool
        logger.info(f"工具已注册: {tool.name} [{tool.category}]")

    def get(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)

    def list_tools(self, category: Optional[ToolCategory] = None) -> list[Tool]:
        """列出工具（可按类别过滤）"""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    def list_names(self, category: Optional[ToolCategory] = None) -> list[str]:
        """列出工具名"""
        return [t.name for t in self.list_tools(category)]

    def get_langchain_tools(self, names: Optional[list[str]] = None) -> list:
        """获取 LangChain 格式的工具列表"""
        tools = self._tools.values()
        if names:
            tools = [t for t in tools if t.name in names]
        result = []
        for tool in tools:
            lc_tool = tool.to_langchain()
            if lc_tool:
                result.append(lc_tool)
        return result

    def _validate_path(self, path: str) -> str:
        """验证路径安全性，返回绝对路径"""
        abs_path = os.path.realpath(os.path.join(self._workspace_root, path))
        real_workspace = os.path.realpath(self._workspace_root)
        if abs_path != real_workspace and not abs_path.startswith(real_workspace + os.sep):
            raise ValueError(f"路径不在允许的工作目录内: {path}")
        return abs_path

    def _register_builtins(self):
        """注册内置工具"""

        # ---- 文件操作 ----

        def file_read(path: str, start_line: int = None, end_line: int = None) -> str:
            """读取文件内容"""
            try:
                if isinstance(start_line, str):
                    start_line = int(start_line) if start_line.strip() else None
                if isinstance(end_line, str):
                    end_line = int(end_line) if end_line.strip() else None
                full_path = self._validate_path(path)
                with open(full_path, "r", errors="ignore") as f:
                    lines = f.readlines()
                if start_line is not None and end_line is not None:
                    lines = lines[start_line - 1:end_line]
                elif start_line is not None:
                    lines = lines[start_line - 1:]
                elif end_line is not None:
                    lines = lines[:end_line]
                content = "".join(lines)
                if len(content) > 10000:
                    content = content[:10000] + f"\n... (截断，共{len(lines)}行)"
                return content
            except Exception as e:
                return f"读取错误: {e}"

        def file_create(path: str, content: str) -> str:
            """创建新文件"""
            try:
                full_path = self._validate_path(path)
                if os.path.exists(full_path):
                    return json.dumps({"error": f"文件已存在: {path}"})
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w") as f:
                    f.write(content)
                return json.dumps({"success": True, "message": f"已创建: {path}"})
            except Exception as e:
                return json.dumps({"error": str(e)})

        def file_update(path: str, content: str) -> str:
            """修改文件内容"""
            try:
                full_path = self._validate_path(path)
                if not os.path.exists(full_path):
                    return json.dumps({"error": f"文件不存在: {path}"})
                with open(full_path, "w") as f:
                    f.write(content)
                return json.dumps({"success": True, "message": f"已更新: {path}"})
            except Exception as e:
                return json.dumps({"error": str(e)})

        def file_delete(path: str, confirm: bool = True) -> str:
            """删除文件"""
            try:
                if not confirm:
                    return json.dumps({"error": "需要确认"})
                full_path = self._validate_path(path)
                if not os.path.exists(full_path):
                    return json.dumps({"error": f"文件不存在: {path}"})
                if os.path.isdir(full_path):
                    return json.dumps({"error": "不能删除目录"})
                os.remove(full_path)
                return json.dumps({"success": True, "message": f"已删除: {path}"})
            except Exception as e:
                return json.dumps({"error": str(e)})

        def file_search(query: str, directory: str = ".") -> str:
            """搜索文件内容"""
            try:
                search_dir = self._validate_path(directory)
                results = []
                for root, dirs, files in os.walk(search_dir):
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "node_modules", "venv")]
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        try:
                            with open(fpath, "r", errors="ignore") as f:
                                for i, line in enumerate(f, 1):
                                    if query.lower() in line.lower():
                                        rel = os.path.relpath(fpath, self._workspace_root)
                                        results.append(f"{rel}:{i}: {line.strip()[:100]}")
                                        if len(results) >= 50:
                                            return json.dumps({"matches": results, "truncated": True})
                        except Exception:
                            continue
                return json.dumps({"matches": results, "total": len(results)})
            except Exception as e:
                return json.dumps({"error": str(e)})

        def file_find(pattern: str, directory: str = ".", use_regex: bool = False) -> str:
            """按文件名搜索"""
            try:
                search_dir = self._validate_path(directory)
                matches = []
                for root, dirs, files in os.walk(search_dir):
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "node_modules", "venv")]
                    for fname in files:
                        matched = bool(re.search(pattern, fname)) if use_regex else fnmatch.fnmatch(fname.lower(), pattern.lower())
                        if matched:
                            rel = os.path.relpath(os.path.join(root, fname), self._workspace_root)
                            matches.append(rel)
                            if len(matches) >= 100:
                                return json.dumps({"files": matches, "truncated": True})
                return json.dumps({"files": matches, "total": len(matches)})
            except Exception as e:
                return json.dumps({"error": str(e)})

        # ---- 终端 ----

        DANGEROUS_COMMANDS = ["rm -rf /", "mkfs", "dd if=", ":(){:|:&};:", "> /dev/sd"]

        def terminal_execute(command: str, working_directory: str = None, timeout: int = 30) -> str:
            """执行终端命令"""
            try:
                for dc in DANGEROUS_COMMANDS:
                    if dc in command.lower():
                        return json.dumps({"error": f"危险命令被阻止: {command}"})
                cwd = self._workspace_root
                if working_directory:
                    cwd = self._validate_path(working_directory)
                timeout = min(timeout, 120)
                result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=cwd, timeout=timeout)
                return json.dumps({
                    "exit_code": result.returncode,
                    "stdout": (result.stdout or "")[:10000],
                    "stderr": (result.stderr or "")[:5000],
                }, ensure_ascii=False)
            except subprocess.TimeoutExpired:
                return json.dumps({"error": f"超时({timeout}s)"})
            except Exception as e:
                return json.dumps({"error": str(e)})

        # ---- 注册所有内置工具 ----

        builtin_tools = [
            Tool(
                name="file_read", description="读取文件内容，可指定行范围",
                category=ToolCategory.FILE, func=file_read,
                parameters={"path": "str", "start_line": "int?", "end_line": "int?"},
            ),
            Tool(
                name="file_create", description="创建新文件",
                category=ToolCategory.FILE, func=file_create,
                parameters={"path": "str", "content": "str"},
            ),
            Tool(
                name="file_update", description="修改已有文件内容",
                category=ToolCategory.FILE, func=file_update,
                parameters={"path": "str", "content": "str"},
            ),
            Tool(
                name="file_delete", description="删除文件",
                category=ToolCategory.FILE, func=file_delete,
                parameters={"path": "str", "confirm": "bool"},
                dangerous=True, requires_confirm=True,
            ),
            Tool(
                name="file_search", description="搜索文件内容中的关键字",
                category=ToolCategory.SEARCH, func=file_search,
                parameters={"query": "str", "directory": "str?"},
            ),
            Tool(
                name="file_find", description="按文件名模式搜索",
                category=ToolCategory.SEARCH, func=file_find,
                parameters={"pattern": "str", "directory": "str?", "use_regex": "bool?"},
            ),
            Tool(
                name="terminal_execute", description="执行终端Shell命令",
                category=ToolCategory.TERMINAL, func=terminal_execute,
                parameters={"command": "str", "working_directory": "str?", "timeout": "int?"},
                dangerous=True,
            ),
        ]

        for tool in builtin_tools:
            self.register(tool)


# 全局工具注册表（延迟初始化，需要 workspace_root）
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry(workspace_root: str = ".") -> ToolRegistry:
    """获取全局工具注册表（单例）"""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry(workspace_root)
    return _tool_registry


def reset_tool_registry():
    """重置全局工具注册表（用于测试）"""
    global _tool_registry
    _tool_registry = None
