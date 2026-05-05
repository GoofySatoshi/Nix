import json
import logging
import os
import re
import fnmatch
import subprocess
import time
from typing import Optional, List

logger = logging.getLogger(__name__)

# ===== 可选导入 tiktoken =====
try:
    import tiktoken
except ImportError:
    tiktoken = None
    logger.info("tiktoken 未安装，上下文 token 计数将使用字符估算 fallback")

# ===== 安全导入 langchain 相关模块 =====

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None
    logger.warning("无法导入 langchain_openai.ChatOpenAI")

try:
    from langchain.agents import AgentExecutor, create_openai_tools_agent
except ImportError:
    AgentExecutor = None
    create_openai_tools_agent = None
    logger.warning("无法导入 AgentExecutor / create_openai_tools_agent，将使用手动工具调用循环")

try:
    from langchain_core.tools import StructuredTool
except ImportError:
    StructuredTool = None
    logger.warning("无法导入 StructuredTool")

try:
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
except ImportError:
    ChatPromptTemplate = None
    MessagesPlaceholder = None
    logger.warning("无法导入 ChatPromptTemplate / MessagesPlaceholder")

try:
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
except ImportError:
    HumanMessage = None
    AIMessage = None
    SystemMessage = None
    ToolMessage = None
    logger.warning("无法导入 langchain_core.messages")

from pydantic import BaseModel, Field


# ===== 兼容层：模拟 AgentAction =====

class AgentAction:
    """兼容 langchain agents 的 Action 对象"""
    def __init__(self, tool: str, tool_input: dict):
        self.tool = tool
        self.tool_input = tool_input


# ===== 工具参数Schema定义 =====


class FileSearchParams(BaseModel):
    query: str = Field(description="搜索关键字")
    directory: str = Field(default=".", description="搜索目录路径")


class FileReadParams(BaseModel):
    path: str = Field(description="文件路径")
    start_line: Optional[int] = Field(default=None, description="起始行号")
    end_line: Optional[int] = Field(default=None, description="结束行号")


class FileCreateParams(BaseModel):
    path: str = Field(description="文件路径")
    content: str = Field(description="文件内容")


class FileUpdateParams(BaseModel):
    path: str = Field(description="文件路径")
    content: str = Field(description="新的文件内容")


class FileDeleteParams(BaseModel):
    path: str = Field(description="文件路径")
    confirm: bool = Field(default=True, description="确认删除")


class TerminalParams(BaseModel):
    command: str = Field(description="要执行的终端命令")
    working_directory: Optional[str] = Field(default=None, description="工作目录")
    timeout: int = Field(default=30, description="超时秒数")


class FileFindParams(BaseModel):
    pattern: str = Field(description="文件名搜索模式")
    directory: str = Field(default=".", description="搜索目录")
    use_regex: bool = Field(default=False, description="是否使用正则表达式")


class SkillCreateParams(BaseModel):
    name: str = Field(description="技能名称，简短描述性的")
    description: str = Field(description="技能的简要描述，说明这个技能做什么")
    content: str = Field(description="技能详细内容，Markdown格式的经验/指令/规范")
    scope: str = Field(description="技能范围：agent（绑定当前智能体，跨项目生效）或 project（仅当前项目生效，存入.nix/skills/）")
    keywords: list = Field(description="触发关键词列表，用于后续自动匹配相关技能")
    category: str = Field(default="general", description="分类标签，如 coding、debug、review、deploy 等")


def _get_workspace_root() -> str:
    """获取工作空间根目录"""
    result = os.environ.get(
        "WORKSPACE_ROOT",
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    logger.info(f"[ChatAgent._get_workspace_root] 返回: {result}")
    return result


def _validate_path(path: str, workspace_root: str) -> str:
    """验证路径在工作目录内，返回绝对路径"""
    logger.info(f"[ChatAgent._validate_path] 入参: path={path}, workspace_root={workspace_root}")
    abs_path = os.path.realpath(os.path.join(workspace_root, path))
    real_workspace = os.path.realpath(workspace_root)
    if abs_path != real_workspace and not abs_path.startswith(real_workspace + os.sep):
        raise ValueError(f"路径不在允许的工作目录内: {path}")
    logger.info(f"[ChatAgent._validate_path] 返回: {abs_path}")
    return abs_path


def create_mcp_tools(workspace_root: str = "."):
    """将MCP工具函数包装为LangChain StructuredTool"""
    logger.info(f"[ChatAgent.create_mcp_tools] 入参: workspace_root={workspace_root}")
    if StructuredTool is None:
        logger.warning("StructuredTool 不可用，返回空工具列表")
        return []

    WORKSPACE_ROOT = os.path.abspath(workspace_root) if workspace_root != "." else _get_workspace_root()

    def validate_path(path: str) -> str:
        """验证路径安全性"""
        return _validate_path(path, WORKSPACE_ROOT)

    # 文件搜索工具
    def file_search(query: str, directory: str = ".") -> str:
        """在工作目录中搜索包含关键字的文件，返回匹配的文件路径和行号"""
        try:
            search_dir = validate_path(directory)
            results = []
            for root, dirs, files in os.walk(search_dir):
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".")
                    and d != "__pycache__"
                    and d != "node_modules"
                    and d != "venv"
                ]
                for fname in files:
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "r", errors="ignore") as f:
                            for i, line in enumerate(f, 1):
                                if query.lower() in line.lower():
                                    rel = os.path.relpath(fpath, WORKSPACE_ROOT)
                                    results.append(f"{rel}:{i}: {line.strip()[:100]}")
                                    if len(results) >= 50:
                                        return json.dumps(
                                            {"matches": results, "truncated": True},
                                            ensure_ascii=False,
                                        )
                    except Exception:
                        continue
            return json.dumps(
                {"matches": results, "total": len(results)}, ensure_ascii=False
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    # 文件读取工具
    def file_read(path: str, start_line: int = None, end_line: int = None) -> str:
        """读取文件内容，可指定行范围"""
        try:
            # 参数类型转换（处理 LLM 可能返回的字符串）
            if isinstance(start_line, str):
                start_line = int(start_line) if start_line.strip() else None
            if isinstance(end_line, str):
                end_line = int(end_line) if end_line.strip() else None

            full_path = validate_path(path)
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
                content = content[:10000] + "\n... (内容被截断，共{}行)".format(
                    len(lines)
                )
            return content
        except Exception as e:
            logger.error(f"file_read执行失败 - path: {path}, start: {start_line}, end: {end_line}, error: {e}")
            return f"文件读取错误: {str(e)}"

    # 文件创建工具
    def file_create(path: str, content: str) -> str:
        """创建新文件"""
        try:
            full_path = validate_path(path)
            parent_dir = os.path.dirname(full_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            if os.path.exists(full_path):
                return json.dumps({"error": f"文件已存在: {path}"})
            with open(full_path, "w") as f:
                f.write(content)
            return json.dumps(
                {"success": True, "message": f"文件已创建: {path}"}
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    # 文件修改工具
    def file_update(path: str, content: str) -> str:
        """修改已有文件内容"""
        try:
            full_path = validate_path(path)
            if not os.path.exists(full_path):
                return json.dumps({"error": f"文件不存在: {path}"})
            with open(full_path, "w") as f:
                f.write(content)
            return json.dumps(
                {"success": True, "message": f"文件已更新: {path}"}
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    # 文件删除工具
    def file_delete(path: str, confirm: bool = True) -> str:
        """删除文件"""
        try:
            if not confirm:
                return json.dumps({"error": "需要确认才能删除"})
            full_path = validate_path(path)
            if not os.path.exists(full_path):
                return json.dumps({"error": f"文件不存在: {path}"})
            if os.path.isdir(full_path):
                return json.dumps({"error": "不能删除目录，仅支持删除文件"})
            os.remove(full_path)
            return json.dumps(
                {"success": True, "message": f"文件已删除: {path}"}
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    # 终端命令执行工具
    def terminal_execute(
        command: str, working_directory: str = None, timeout: int = 30
    ) -> str:
        """在终端执行命令"""
        try:
            # 危险命令检查
            dangerous_commands = [
                "rm -rf /",
                "mkfs",
                "dd if=",
                ":(){:|:&};:",
                "fork bomb",
            ]
            for dc in dangerous_commands:
                if dc in command.lower():
                    return json.dumps(
                        {"error": f"危险命令被阻止: {command}"}
                    )

            cwd = WORKSPACE_ROOT
            if working_directory:
                cwd = validate_path(working_directory)
                if not os.path.isdir(cwd):
                    return json.dumps(
                        {"error": f"工作目录不存在: {working_directory}"}
                    )

            timeout = min(timeout, 120)
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout,
            )
            stdout = result.stdout[:10000] if result.stdout else ""
            stderr = result.stderr[:5000] if result.stderr else ""
            return json.dumps(
                {
                    "exit_code": result.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                },
                ensure_ascii=False,
            )
        except subprocess.TimeoutExpired:
            return json.dumps({"error": f"命令超时({timeout}秒)"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    # 文件名搜索工具
    def file_find(
        pattern: str, directory: str = ".", use_regex: bool = False
    ) -> str:
        """按文件名搜索文件"""
        try:
            search_dir = validate_path(directory)
            matches = []
            for root, dirs, files in os.walk(search_dir):
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".")
                    and d != "__pycache__"
                    and d != "node_modules"
                    and d != "venv"
                ]
                for fname in files:
                    matched = False
                    if use_regex:
                        matched = bool(re.search(pattern, fname))
                    else:
                        matched = fnmatch.fnmatch(fname.lower(), pattern.lower())
                    if matched:
                        rel = os.path.relpath(
                            os.path.join(root, fname), WORKSPACE_ROOT
                        )
                        matches.append(rel)
                        if len(matches) >= 100:
                            return json.dumps(
                                {"files": matches, "truncated": True}
                            )
            return json.dumps({"files": matches, "total": len(matches)})
        except Exception as e:
            return json.dumps({"error": str(e)})

    # 技能创建工具
    def skill_create(name: str, description: str, content: str, scope: str,
                     keywords: list = None, category: str = "general") -> str:
        """创建一个新的技能（经验内化）。scope=agent 绑定当前智能体跨项目生效，scope=project 存入当前项目 .nix/skills/ 目录"""
        try:
            from models.database import get_db
            from models.skill import Skill
            from services.skill_service import write_skill_file

            # 验证 scope
            if scope not in ("agent", "project"):
                return f"错误：scope 必须是 'agent' 或 'project'，收到 '{scope}'"

            # 获取数据库会话
            db = next(get_db())
            try:
                # 创建数据库记录
                new_skill = Skill(
                    name=name,
                    description=description,
                    content=content,
                    scope=scope,
                    keywords=keywords or [],
                    category=category,
                    agent_id=None,  # 将在调用时由上层设置
                    is_active=True,
                )
                db.add(new_skill)
                db.commit()
                db.refresh(new_skill)

                result = f"✅ 技能 '{name}' 创建成功（ID: {new_skill.id}，范围: {scope}）"

                # 项目级 skill 同步写入文件
                if scope == "project":
                    # workspace 通过全局变量或默认路径获取
                    import os
                    workspace = os.environ.get("NIX_WORKSPACE", os.getcwd())
                    file_path = write_skill_file(workspace, name, description, keywords or [], category, content)
                    result += f"\n📄 已同步写入文件: {file_path}"

                return result
            finally:
                db.close()
        except Exception as e:
            return f"❌ 创建技能失败: {str(e)}"

    # 构建LangChain工具列表
    tools = [
        StructuredTool.from_function(
            func=file_search,
            name="file_search",
            description="在工作目录中搜索包含指定关键字的文件内容，返回匹配的文件路径和行号。适合查找代码、配置或文本内容。",
            args_schema=FileSearchParams,
        ),
        StructuredTool.from_function(
            func=file_read,
            name="file_read",
            description="读取指定文件的内容。可以指定起始行和结束行来读取部分内容。",
            args_schema=FileReadParams,
        ),
        StructuredTool.from_function(
            func=file_create,
            name="file_create",
            description="在工作目录中创建新文件。需要指定文件路径和内容。",
            args_schema=FileCreateParams,
        ),
        StructuredTool.from_function(
            func=file_update,
            name="file_update",
            description="修改已有文件的内容。需要指定文件路径和新内容。",
            args_schema=FileUpdateParams,
        ),
        StructuredTool.from_function(
            func=file_delete,
            name="file_delete",
            description="删除指定的文件。",
            args_schema=FileDeleteParams,
        ),
        StructuredTool.from_function(
            func=terminal_execute,
            name="terminal_execute",
            description="在终端执行Shell命令。可以运行任何终端命令来完成任务，如安装依赖、运行脚本、查看系统信息等。注意：这是macOS环境，使用zsh shell。",
            args_schema=TerminalParams,
        ),
        StructuredTool.from_function(
            func=file_find,
            name="file_find",
            description="按文件名搜索文件。支持通配符（如 *.py）和正则表达式匹配。",
            args_schema=FileFindParams,
        ),
        StructuredTool.from_function(
            func=skill_create,
            name="skill_create",
            description="创建新技能（经验内化）。当你总结出可复用的经验、规范或最佳实践时，调用此工具保存为技能。scope=agent 跨项目生效，scope=project 仅当前项目。",
            args_schema=SkillCreateParams,
        ),
    ]

    logger.info(f"[ChatAgent.create_mcp_tools] 返回: {len(tools)} 个工具")
    return tools


# ===== 意图识别层 =====

class IntentType:
    """用户意图类型"""
    GENERAL_CHAT = "general_chat"          # 普通对话/闲聊/问答
    FILE_OPERATION = "file_operation"       # 文件操作（创建/修改/删除/搜索）
    CODE_ANALYSIS = "code_analysis"         # 代码分析/理解/解释
    TERMINAL_COMMAND = "terminal_command"   # 终端命令执行
    PROJECT_TASK = "project_task"           # 复合项目任务（涉及多步骤）
    INFORMATION_QUERY = "information_query" # 信息查询/知识问答
    CODE_REVIEW = "code_review"             # 代码审查/质量检查
    CODE_GENERATION = "code_generation"     # 代码生成/编写
    PROJECT_ANALYSIS = "project_analysis"   # 项目结构/架构分析





def create_intent_llm(api_key: str, model: str, base_url: str = None):
    """创建专门用于意图识别的独立 LLM 实例（不绑定工具，低配置）"""
    logger.info(f"[ChatAgent.create_intent_llm] 入参: model={model}, base_url={base_url}")
    if ChatOpenAI is None:
        logger.info("[ChatAgent.create_intent_llm] 返回: None (ChatOpenAI不可用)")
        return None
    try:
        kwargs = {
            "api_key": api_key,
            "model": model,
            "temperature": 0.3,
            "max_tokens": 4000,
            "timeout": 300,
        }
        if base_url:
            kwargs["base_url"] = base_url
        result = ChatOpenAI(**kwargs)
        logger.info(f"[ChatAgent.create_intent_llm] 返回: LLM实例(model={model})")
        return result
    except Exception as e:
        logger.warning(f"创建意图识别 LLM 失败: {e}")
        return None


def _get_project_context(task_description: str = "") -> str:
    """获取项目上下文信息，帮助生成更精准的执行计划"""
    logger.info(f"[ChatAgent._get_project_context] 入参: task_description={task_description if task_description else ''}")
    context_parts = []

    # 读取环境配置
    env_path = os.path.join(os.path.dirname(__file__), '..', '.nix', 'environment.json')
    workspace_path = None
    try:
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                env_config = json.load(f)
                workspace_path = env_config.get('workspace_path', '')
                if workspace_path:
                    context_parts.append(f"工作目录: {workspace_path}")
    except Exception as e:
        logger.warning(f"[ChatAgent._get_project_context] 读取环境配置失败: {e}")

    # 扫描项目结构（最多2层）
    if workspace_path and os.path.isdir(workspace_path):
        tree_lines = []
        try:
            for item in sorted(os.listdir(workspace_path)):
                if item.startswith('.') or item in ('node_modules', 'venv', '__pycache__', 'build', 'dist'):
                    continue
                item_path = os.path.join(workspace_path, item)
                if os.path.isdir(item_path):
                    tree_lines.append(f"  {item}/")
                    # 第二层
                    try:
                        for sub in sorted(os.listdir(item_path))[:10]:
                            if sub.startswith('.') or sub in ('node_modules', 'venv', '__pycache__', 'build', 'dist'):
                                continue
                            tree_lines.append(f"    {sub}")
                    except PermissionError:
                        pass
                else:
                    tree_lines.append(f"  {item}")
            if tree_lines:
                context_parts.append(f"项目结构:\n" + "\n".join(tree_lines[:50]))
        except Exception as e:
            logger.warning(f"[ChatAgent._get_project_context] 扫描项目结构失败: {e}")

    # 读取项目描述文件
    if workspace_path:
        for doc_name in ['ARCHITECTURE.md', 'README.md']:
            doc_path = os.path.join(workspace_path, doc_name)
            try:
                if os.path.exists(doc_path):
                    with open(doc_path, 'r', encoding='utf-8') as f:
                        doc_content = f.read(800)
                    context_parts.append(f"项目说明({doc_name}):\n{doc_content}")
                    break  # 只取一个
            except Exception as e:
                logger.warning(f"[ChatAgent._get_project_context] 读取{doc_name}失败: {e}")

    result = "\n\n".join(context_parts) if context_parts else "无项目上下文信息"
    logger.info(f"[ChatAgent._get_project_context] 返回: {len(result)} chars")
    return result


def generate_execution_plan(api_key: str, model: str, base_url: str,
                           user_msg: str, intent: str, available_tools: list) -> dict:
    """生成任务执行计划（待办清单）"""
    logger.info(f"[ChatAgent.generate_execution_plan] 入参: model={model}, user_msg={user_msg}, intent={intent}, tools={len(available_tools) if available_tools else 0}")
    if ChatOpenAI is None or HumanMessage is None or SystemMessage is None:
        logger.warning("LLM 或消息类型不可用，返回默认计划")
        return {"steps": [{"name": "执行任务", "description": user_msg[:100]}]}
    try:
        kwargs = {
            "api_key": api_key,
            "model": model,
            "temperature": 0.5,
            "max_tokens": 8000,
            "timeout": 300,
        }
        if base_url:
            kwargs["base_url"] = base_url
        plan_llm = ChatOpenAI(**kwargs)

        tools_str = ", ".join(available_tools) if available_tools else "无"
        
        # 获取项目上下文
        project_context = _get_project_context(user_msg)
        
        system_prompt = f"""你是一个任务规划工程师。将用户需求拆解为可直接执行的步骤。

## 项目上下文（参考此信息确定文件路径和技术方案）
{project_context}

## 可用工具
{tools_str}

## 规则
1. 每步必须对应一个具体的工具操作（创建文件、修改文件、执行命令等）
2. description 必须包含：目标文件路径、具体要写什么代码/内容、技术方案
3. 禁止抽象描述如"实现功能"、"完善代码"，必须写清楚具体做什么
4. 步骤数：简单任务 2-3 步，中等 4-6 步，复杂 6-10 步
5. name 不超过 8 字，动词开头

## 好的 description 示例
- "创建 backend/models/role.py，定义 Role 模型，包含 id, name, permissions 字段，使用 SQLAlchemy"
- "修改 backend/routes/auth.py，新增 POST /api/roles 接口，接收 name 和 permissions 参数"
- "在 frontend/src/components/RoleManager.tsx 中编写角色管理组件，包含列表展示和新增表单"

## 坏的 description（禁止）
- "实现后端接口"  ← 太抽象，什么接口？哪个文件？
- "完善前端页面"  ← 完善什么？
- "测试功能"      ← 测什么？怎么测？

## 输出
严格 JSON，不要其他文字：
{{"steps": [{{"name": "步骤名", "description": "具体操作"}}]}}"""

        response = plan_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_msg)
        ])
        content = response.content.strip() if response.content else ""
        logger.info(f"[Plan] LLM原始返回 ({len(content)} chars): {content}")

        if not content:
            logger.warning("[Plan] LLM返回空内容，使用默认计划")
            return {"steps": [{"name": "执行任务", "description": user_msg[:100]}]}

        # 解析 JSON（可能包裹在 markdown 代码块中）
        json_match = re.search(r'```(?:json)?\s*(.*?)```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1).strip()

        # 尝试提取 JSON 对象
        json_obj_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_obj_match:
            content = json_obj_match.group(0)

        result = json.loads(content)
        if "steps" in result and isinstance(result["steps"], list) and len(result["steps"]) > 0:
            logger.info(f"[ChatAgent.generate_execution_plan] 返回: {len(result['steps'])} 步")
            return result
        else:
            logger.warning("LLM 返回的 JSON 格式不正确，使用默认计划")
            return {"steps": [{"name": "执行任务", "description": user_msg[:100]}]}
    except Exception as e:
        logger.warning(f"生成执行计划失败: {e}")
        return {"steps": [{"name": "执行任务", "description": user_msg[:100]}]}


def classify_intent_llm(llm, message: str) -> str:
    """使用LLM进行意图识别

    注意：为避免意图识别的 token 污染主对话上下文，
    推荐传入通过 create_intent_llm() 创建的独立 LLM 实例。
    """
    logger.info(f"[ChatAgent.classify_intent_llm] 入参: message={message}")
    if HumanMessage is None or SystemMessage is None:
        logger.info("[ChatAgent.classify_intent_llm] 返回: general_chat (消息类型不可用)")
        return IntentType.GENERAL_CHAT

    intent_prompt = """你是一个意图分类器。根据用户消息判断意图类别，只返回类别名称，不要有其他文字。

类别定义：
- project_task: 需要执行的开发任务。包括但不限于：创建新项目、创建新模块、实现新功能、修复bug、优化代码、重构代码、搭建开发环境、设计系统架构、设计数据库表结构、配置服务器等。即使任务很复杂或包含多个子目标，只要涉及代码开发或系统搭建，就是 project_task。
- code_generation: 生成独立的代码片段或脚本，不涉及项目集成。例如："写一个排序算法"、"生成一个正则表达式"
- code_analysis: 分析、解释已有代码，不涉及修改。
- file_operation: 简单文件操作（创建/删除/重命名空文件），不涉及代码编写。
- terminal_command: 执行系统命令（安装依赖、启动服务、查看日志等）。
- project_analysis: 分析项目结构、架构、依赖关系。
- code_review: 代码质量审查。
- information_query: 知识问答、概念解释，不涉及代码操作。
- general_chat: 纯闲聊问候（你好、谢谢、晚安）。

判断规则：
1. 只要用户要求创建、实现、修改、搭建、设计任何代码/系统/模块/项目 → project_task
2. 包含多个子任务但都关于开发 → 仍然是 project_task
3. 不确定时 → project_task

只返回类别名称。"""

    try:
        # 带重试的LLM调用（最多3次尝试）
        max_retries = 3
        raw_content = ""
        for attempt in range(max_retries):
            logger.info(f"[Intent] 第{attempt+1}次调用LLM进行意图识别, 用户消息: {message}")
            response = llm.invoke([
                SystemMessage(content=intent_prompt),
                HumanMessage(content=f"用户消息: {message}")
            ])
            # 打印响应元数据用于调试
            if hasattr(response, 'response_metadata'):
                logger.info(f"[Intent] 响应元数据: {response.response_metadata}")
            raw_content = response.content.strip() if response.content else ""
            if raw_content:
                break
            logger.warning(f"[Intent] 第{attempt+1}次LLM返回空内容，{'重试中...' if attempt < max_retries-1 else '放弃重试'}")
            if attempt < max_retries - 1:
                time.sleep(1)  # 等1秒后重试

        if not raw_content:
            logger.warning(f"[Intent] {max_retries}次重试均返回空内容，使用关键词兜底判断")
            matched = "general_chat"
        else:
            result = raw_content.lower().replace('"', '').replace("'", "")
            logger.info(f"[Intent] LLM原始返回: '{result}', 用户消息: {message}")

            # 验证返回值是否为有效意图
            valid_intents = {
                "general_chat", "file_operation", "code_analysis",
                "terminal_command", "project_task", "information_query",
                "code_review", "code_generation", "project_analysis"
            }
            if result in valid_intents:
                matched = result
            else:
                # 尝试模糊匹配
                matched = None
                for vi in valid_intents:
                    if vi in result:
                        matched = vi
                        break
                if not matched:
                    matched = "general_chat"

        # 兜底纠正：如果 LLM 返回非 project_task 但消息明显包含开发意图，强制纠正
        if matched != "project_task" and len(message) > 15:
            dev_keywords = [
                "创建", "实现", "开发", "搭建", "设计", "修复", "优化", "重构", "改进",
                "添加", "新增", "完成", "部署", "配置", "集成", "迁移", "升级",
                "登录", "注册", "认证", "权限", "角色", "接口", "API", "数据库", "表结构",
                "前端", "后端", "全栈", "架构", "模块", "组件", "页面", "系统",
                "服务", "功能", "特性", "改造", "重写", "整合", "联调", "对接"
            ]
            if any(kw in message for kw in dev_keywords):
                matched_kws = [kw for kw in dev_keywords if kw in message]
                logger.info(f"[Intent] 兜底纠正: {matched} -> project_task (匹配关键词: {matched_kws})")
                matched = "project_task"

        logger.info(f"[ChatAgent.classify_intent_llm] 返回: {matched}")
        return matched
    except Exception as e:
        logger.error(f"[Intent] LLM意图识别异常: {e}")
        return IntentType.GENERAL_CHAT


# 不同意图对应的工具子集和提示增强
INTENT_TOOL_MAP = {
    IntentType.GENERAL_CHAT: [],  # 不需要工具
    IntentType.INFORMATION_QUERY: [],  # 不需要工具
    IntentType.FILE_OPERATION: ["file_search", "file_read", "file_create", "file_update", "file_delete", "file_find"],
    IntentType.CODE_ANALYSIS: ["file_search", "file_read", "file_find"],
    IntentType.TERMINAL_COMMAND: ["terminal_execute"],
    IntentType.PROJECT_TASK: None,  # None 表示使用全部工具
    IntentType.CODE_REVIEW: ["file_search", "file_read", "file_find"],  # 审查只需要读取文件
    IntentType.CODE_GENERATION: ["file_search", "file_read", "file_create", "file_update", "file_find"],  # 生成代码需要读写文件
    IntentType.PROJECT_ANALYSIS: ["file_search", "file_read", "file_find", "terminal_execute"],  # 项目分析可能需要运行命令查看结构
}

INTENT_PROMPT_SUFFIX = {
    IntentType.GENERAL_CHAT: "\n\n当前为普通对话模式，直接回答用户问题即可，无需调用工具。",
    IntentType.INFORMATION_QUERY: "\n\n当前为信息查询模式，基于你的知识回答问题，无需调用工具。",
    IntentType.FILE_OPERATION: "\n\n当前为文件操作模式，请使用文件相关工具完成用户请求。",
    IntentType.CODE_ANALYSIS: "\n\n当前为代码分析模式，请先搜索/读取相关代码，然后给出详细分析。",
    IntentType.TERMINAL_COMMAND: "\n\n当前为终端命令模式，请使用terminal_execute工具执行用户请求的命令。",
    IntentType.PROJECT_TASK: "\n\n当前为项目任务模式，这是一个复合任务，请合理规划步骤，依次使用工具完成。",
    IntentType.CODE_REVIEW: "\n\n你是一个代码审查专家。请仔细阅读用户指定的代码，从代码质量、规范性、潜在bug、安全性等角度给出审查意见。",
    IntentType.CODE_GENERATION: "\n\n你是一个代码生成专家。请根据用户需求生成高质量、规范的代码，包含必要的注释和错误处理。",
    IntentType.PROJECT_ANALYSIS: "\n\n你是一个项目分析专家。请分析项目的结构、架构、技术栈和依赖关系，给出清晰的分析报告。",
}


# ===== 上下文窗口管理器 =====

class ContextManager:
    """上下文窗口管理器"""

    def __init__(self, max_tokens: int = 8000, compress_threshold: float = 0.85):
        self.max_tokens = max_tokens
        self.compress_threshold = compress_threshold  # 达到 85% 时触发压缩
        if tiktoken is not None:
            try:
                self.encoder = tiktoken.get_encoding("cl100k_base")
            except Exception:
                self.encoder = None
        else:
            self.encoder = None
        self.last_compress_time = 0
        self.compress_cooldown = 30  # 压缩后 30 秒内不再触发

    def count_tokens(self, messages: list) -> int:
        """估算消息列表的 token 数"""
        logger.info(f"[ContextManager.count_tokens] 入参: messages数量={len(messages)}")
        if self.encoder is None:
            # fallback: 粗略估算（每3个字符约1个token）
            total_chars = sum(
                len(getattr(m, 'content', '') or str(m)) for m in messages
            )
            return total_chars // 3

        total = 0
        for m in messages:
            content = getattr(m, 'content', '') or str(m)
            total += len(self.encoder.encode(content)) + 4  # 每条消息的开销
        logger.info(f"[ContextManager.count_tokens] 返回: {total} tokens")
        return total

    def should_compress(self, messages: list) -> bool:
        """判断是否需要压缩（含冷却期检查）"""
        logger.info(f"[ContextManager.should_compress] 入参: messages数量={len(messages)}")
        tokens = self.count_tokens(messages)
        if tokens <= self.max_tokens * self.compress_threshold:
            return False
        # 冷却期检查：避免短时间内重复压缩
        now = time.time()
        if now - self.last_compress_time < self.compress_cooldown:
            logger.info("[ContextManager.should_compress] 返回: False (冷却期)")
            return False
        logger.info("[ContextManager.should_compress] 返回: True")
        return True

    def compress_context(self, messages: list) -> list:
        """压缩上下文 - 优先使用AI自输出的摘要"""
        logger.info(f"[ContextManager.compress_context] 入参: messages数量={len(messages)}")
        self.last_compress_time = time.time()

        if not messages:
            return messages

        # 保留 system message
        system_msg = None
        other_msgs = []
        for m in messages:
            if hasattr(m, 'type') and m.type == 'system':
                system_msg = m
            elif isinstance(m, SystemMessage):
                system_msg = m
            else:
                other_msgs.append(m)

        # 从最近的 assistant 消息中提取摘要
        latest_summary = self._extract_latest_summary(messages)

        new_messages = []
        if system_msg:
            new_messages.append(system_msg)

        if latest_summary:
            # 有摘要：用摘要构建新上下文
            new_messages.append(SystemMessage(
                content=f"[上下文恢复] 以下是之前工作的摘要：\n{latest_summary}\n\n请基于此继续工作。"
            ))
            # 保留最近的几条消息（最近6条，排除系统消息）
            recent = other_msgs[-6:] if len(other_msgs) > 6 else other_msgs
            new_messages.extend(recent)
            logger.info(f"上下文已压缩(使用AI摘要): {len(messages)}条 → {len(new_messages)}条")
        else:
            # 没有摘要：使用简单截断策略（保留system + 最近8条）
            recent = other_msgs[-8:] if len(other_msgs) > 8 else other_msgs
            dropped_count = len(other_msgs) - len(recent)
            if dropped_count > 0:
                new_messages.append(SystemMessage(
                    content=f"[上下文提示] earlier {dropped_count} messages were truncated to keep within token limit."
                ))
            new_messages.extend(recent)
            logger.info(f"上下文已截断(fallback): {len(messages)}条 → {len(new_messages)}条")

        logger.info(f"[ContextManager.compress_context] 返回: {len(new_messages)} 条消息")
        return new_messages

    def _extract_latest_summary(self, messages):
        """从最近的assistant消息中提取context_summary"""
        logger.info(f"[ContextManager._extract_latest_summary] 入参: messages数量={len(messages)}")
        for msg in reversed(messages):
            role = getattr(msg, 'type', None)
            if role is None and hasattr(msg, 'role'):
                role = msg.role
            if role in ('assistant', 'ai'):
                content = getattr(msg, 'content', '') or str(msg)
                if isinstance(content, str):
                    match = re.search(r'<context_summary>(.*?)</context_summary>', content, re.DOTALL)
                    if match:
                        summary = match.group(1).strip()
                        logger.info(f"[ContextManager._extract_latest_summary] 返回: 找到摘要 ({len(summary)} chars)")
                        return summary
        logger.info("[ContextManager._extract_latest_summary] 返回: None")
        return None


def _strip_context_summary(text: str) -> str:
    """从AI回复中移除上下文摘要和工具调用标记"""
    logger.info(f"[ChatAgent._strip_context_summary] 入参: text长度={len(text) if text else 0}")
    if not text:
        return text

    # 移除 <context_summary> 标签
    text = re.sub(r'<context_summary>.*?</context_summary>', '', text, flags=re.DOTALL)

    # 移除 <function_calls> 及其内部的工具调用标记
    text = re.sub(r'<function_calls>.*?</function_calls>', '', text, flags=re.DOTALL)

    # 移除不完整的 function_calls 标记（只有开始标签没有结束标签的情况）
    text = re.sub(r'<function_calls>.*', '', text, flags=re.DOTALL)

    # 移除孤立的 invoke/parameter 标记
    text = re.sub(r'<invoke[^>]*>.*?</invoke>', '', text, flags=re.DOTALL)
    text = re.sub(r'<parameter[^>]*>.*?</parameter>', '', text, flags=re.DOTALL)

    # 移除类似变体标记（有些模型可能用略有不同的格式）
    text = re.sub(r'<｜DSML｜function_calls>.*', '', text, flags=re.DOTALL)
    text = re.sub(r'<｜DSML｜[^>]*>.*', '', text, flags=re.DOTALL)

    # 格式3: <tool_call>...</tool_call> 和不完整的 <tool_call>...
    text = re.sub(r'<tool_call>.*?</tool_call>', '', text, flags=re.DOTALL)
    text = re.sub(r'<tool_call>.*', '', text, flags=re.DOTALL)

    # 格式4: <function=xxx>...</function>
    text = re.sub(r'<function=[^>]*>.*?</function>', '', text, flags=re.DOTALL)
    text = re.sub(r'<function=[^>]*>.*', '', text, flags=re.DOTALL)

    # 格式5: <parameter=xxx>...</parameter>（带属性的独立出现）
    text = re.sub(r'<parameter=[^>]*>.*?</parameter>', '', text, flags=re.DOTALL)

    # 格式6: <|plugin|> 或 <|interpreter|> 等特殊 token
    text = re.sub(r'<\|(?:plugin|interpreter|action|tool_call|function_call)\|>.*', '', text, flags=re.DOTALL)

    # 如果清理后为空，返回一个默认提示
    cleaned = text.strip()
    if not cleaned:
        cleaned = "任务已完成。"

    logger.info(f"[ChatAgent._strip_context_summary] 返回: {len(cleaned)} chars")
    return cleaned


# ===== 手动 Agent Executor（兼容层）=====

class ManualAgentExecutor:
    """当 AgentExecutor 不可用时，使用手动工具调用循环实现兼容的 invoke 接口"""

    def __init__(self, llm, tools, system_prompt: str, api_key: str = None, model: str = None, base_url: str = None, intent_model: str = None):
        self.llm = llm
        self.tools = tools
        self.system_prompt = system_prompt
        self.tool_map = {t.name: t for t in tools}
        self.context_manager = ContextManager(max_tokens=8000)
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.intent_model = intent_model
        try:
            self.llm_with_tools = llm.bind_tools(tools)
        except Exception as e:
            logger.warning(f"bind_tools 失败: {e}")
            self.llm_with_tools = llm

    def invoke(self, inputs: dict, max_iterations: int = 50) -> dict:
        """手动工具调用循环，返回与 AgentExecutor 兼容的结果格式"""
        logger.info(f"[ManualAgentExecutor.invoke] 入参: input={str(inputs.get('input', ''))}, max_iterations={max_iterations}, history_len={len(inputs.get('chat_history', []))}")
        if HumanMessage is None or SystemMessage is None or ToolMessage is None:
            raise RuntimeError("langchain_core.messages 不可用，无法运行手动 Agent")

        input_text = inputs.get("input", "")
        chat_history = inputs.get("chat_history", [])

        # === 意图识别（完全使用 LLM） ===
        intent_llm = None
        if self.api_key and self.model:
            _intent_model = self.intent_model or self.model
            intent_llm = create_intent_llm(self.api_key, _intent_model, self.base_url)
        if intent_llm:
            intent = classify_intent_llm(intent_llm, input_text)
            logger.info(f"使用独立 LLM 识别意图: {intent}")
        else:
            intent = classify_intent_llm(self.llm, input_text)
            logger.info(f"使用主 LLM 识别意图(fallback): {intent}")

        # === 意图路由 ===
        # 对于不需要工具的意图，直接用LLM回答
        if intent in (IntentType.GENERAL_CHAT, IntentType.INFORMATION_QUERY):
            try:
                messages = []
                if self.system_prompt:
                    messages.append(SystemMessage(content=self.system_prompt + INTENT_PROMPT_SUFFIX.get(intent, "")))
                if chat_history:
                    messages.extend(chat_history)
                messages.append(HumanMessage(content=input_text))
                response = self.llm.invoke(messages)
                return {
                    "output": _strip_context_summary(response.content or ""),
                    "intermediate_steps": [],
                    "intent": intent,
                }
            except Exception as e:
                logger.error(f"直接对话失败: {e}")
                return {"output": f"对话失败: {e}", "intermediate_steps": [], "intent": intent}

        # === 对于需要工具的意图，筛选工具子集 ===
        allowed_tools = INTENT_TOOL_MAP.get(intent)
        if allowed_tools is not None:
            filtered_tools = [t for t in self.tools if t.name in allowed_tools]
            tool_map = {t.name: t for t in filtered_tools}
            try:
                llm_with_tools = self.llm.bind_tools(filtered_tools) if filtered_tools else self.llm
            except Exception:
                llm_with_tools = self.llm_with_tools
        else:
            filtered_tools = self.tools
            tool_map = self.tool_map
            llm_with_tools = self.llm_with_tools

        # 构建带意图增强的消息
        enhanced_system = self.system_prompt + INTENT_PROMPT_SUFFIX.get(intent, "")
        current_messages = []
        if enhanced_system:
            current_messages.append(SystemMessage(content=enhanced_system))
        if chat_history:
            current_messages.extend(chat_history)
        current_messages.append(HumanMessage(content=input_text))

        intermediate_steps = []

        # === 工具调用循环 ===
        for i in range(max_iterations):
            # 检查是否需要压缩上下文
            if self.context_manager.should_compress(current_messages):
                logger.info(f"第{i}轮: 上下文接近上限，执行压缩...")
                current_messages = self.context_manager.compress_context(
                    current_messages
                )

            try:
                response = llm_with_tools.invoke(current_messages)
            except Exception as e:
                logger.error(f"LLM invoke 失败: {e}")
                return {"output": f"模型调用失败: {e}", "intermediate_steps": intermediate_steps, "intent": intent}

            # 检查是否有 tool_calls
            tool_calls = getattr(response, "tool_calls", None)
            if not tool_calls:
                return {
                    "output": _strip_context_summary(response.content or ""),
                    "intermediate_steps": intermediate_steps,
                    "intent": intent,
                }

            # 处理工具调用
            current_messages.append(response)
            for tc in tool_calls:
                tool_name = tc.get("name") or tc.get("function", {}).get("name")
                tool_args = tc.get("args") or tc.get("function", {}).get("arguments", {})
                tool_call_id = tc.get("id", "")

                tool_fn = tool_map.get(tool_name)
                if tool_fn:
                    try:
                        result = tool_fn.invoke(tool_args)
                    except Exception as e:
                        result = f"工具执行错误: {e}"
                else:
                    result = f"工具 {tool_name} 未找到"

                # 构建兼容的 intermediate_steps 格式
                action = AgentAction(tool=tool_name, tool_input=tool_args if isinstance(tool_args, dict) else {"input": tool_args})
                intermediate_steps.append((action, str(result)))

                current_messages.append(
                    ToolMessage(content=str(result), tool_call_id=tool_call_id)
                )

        # 达到最大迭代次数，尝试让LLM做最终总结
        try:
            summary_prompt = "你已经执行了多个工具调用。请根据以上所有工具调用的结果，给用户一个完整的总结回复。不要再调用任何工具。"
            current_messages.append(HumanMessage(content=summary_prompt))
            # 用不绑定工具的 llm 调用，避免再次触发工具
            final_response = self.llm.invoke(current_messages)
            final_output = final_response.content or ""
        except Exception as e:
            # 如果总结也失败，手动拼接结果
            summaries = []
            for action, obs in intermediate_steps:
                summaries.append(f"[{action.tool}] {str(obs)[:200]}")
            final_output = "工具调用结果摘要：\n" + "\n".join(summaries)

        return {
            "output": _strip_context_summary(final_output),
            "intermediate_steps": intermediate_steps,
            "intent": intent,
        }


def create_chat_agent_executor(
    api_key: str,
    model: str,
    base_url: str = None,
    workspace_root: str = ".",
    env_summary: str = "",
    intent_model: str = None,
):
    """创建带MCP工具的对话Agent"""
    logger.info(f"[ChatAgent.create_chat_agent_executor] 入参: model={model}, base_url={base_url}, workspace_root={workspace_root}, intent_model={intent_model}")

    if ChatOpenAI is None:
        logger.warning("ChatOpenAI 不可用，无法创建 Agent")
        return None

    try:
        llm = ChatOpenAI(
            api_key=api_key,
            model=model,
            base_url=base_url if base_url else None,
            temperature=0.7,
            max_tokens=4096,
            timeout=60,
        )
    except Exception as e:
        logger.error(f"创建 LLM 失败: {e}")
        return None

    tools = create_mcp_tools(workspace_root)

    env_info = f"当前环境信息：\n{env_summary}" if env_summary else ""

    system_prompt = f"""你是一个强大的AI助手，可以通过工具来帮助用户完成各种任务。

你拥有以下工具能力：
- file_search: 搜索文件内容
- file_read: 读取文件
- file_create: 创建文件
- file_update: 修改文件
- file_delete: 删除文件
- terminal_execute: 执行终端命令
- file_find: 按文件名搜索
- skill_create: 创建新技能（经验内化）

当用户要求你操作文件、执行命令或查看代码时，请主动使用这些工具来完成任务。
不要假装执行，要真正调用工具。执行完后告知用户结果。

{env_info}

重要规则：
1. 所有文件操作限制在工作目录内
2. 执行危险命令前要告知用户
3. 修改/删除文件前先确认
4. 终端命令需符合当前操作系统
5. 尽量在10步以内完成任务并给出总结，不要无限循环调用工具
6. 当你完成一个复杂任务后，如果总结出了可复用的经验或规范，主动使用 skill_create 工具将其保存为技能

当你完成一个工具调用序列或完成一轮较长的任务后，请在回复末尾用 <context_summary> 标签输出当前工作状态的简要摘要，包括：
1. 当前正在处理的任务和进度
2. 已完成的关键操作和结果
3. 待处理的后续步骤
4. 重要的上下文信息（如文件路径、变量值等）
格式：<context_summary>摘要内容</context_summary>
这个摘要会在上下文空间不足时用于快速恢复工作状态。"""

    # 方式1: 使用原生 AgentExecutor（如果可用）
    if AgentExecutor is not None and create_openai_tools_agent is not None and ChatPromptTemplate is not None and MessagesPlaceholder is not None:
        try:
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", system_prompt),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{input}"),
                    MessagesPlaceholder(variable_name="agent_scratchpad"),
                ]
            )
            agent = create_openai_tools_agent(llm, tools, prompt)
            executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=True,
                max_iterations=50,
                handle_parsing_errors=True,
                return_intermediate_steps=True,
            )
            return executor
        except Exception as e:
            logger.warning(f"原生 AgentExecutor 创建失败，回退到手动循环: {e}")

    # 方式2: 使用手动工具调用循环（bind_tools 方式）
    if tools and HumanMessage is not None and ToolMessage is not None:
        try:
            executor = ManualAgentExecutor(
                llm, tools, system_prompt,
                api_key=api_key, model=model, base_url=base_url, intent_model=intent_model
            )
            return executor
        except Exception as e:
            logger.error(f"手动 AgentExecutor 创建失败: {e}")
            return None

    logger.warning("无法创建任何类型的 Agent Executor")
    return None

