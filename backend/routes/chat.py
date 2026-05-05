import asyncio
import json
import logging
import re
import time
from functools import partial
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from models import ApiKeyConfig, get_db, User, Task, Agent, Message
from models.system_settings import SystemSettings
from datetime import datetime
from schemas.chat import ChatRequest, ChatResponse, ChatConfigItem, ToolCallTrace
from dependencies.auth import get_current_user
from services.llm_service import get_llm_for_config
from services.skill_service import load_relevant_skills
from services.chat_agent import create_chat_agent_executor, _strip_context_summary, generate_execution_plan
from services.acceptance_service import run_acceptance_check
from models.workflow import WorkflowStep

try:
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
except ImportError:
    HumanMessage = None
    AIMessage = None
    SystemMessage = None

logger = logging.getLogger(__name__)
router = APIRouter()


def _is_tool_success(result) -> bool:
    """判断工具执行是否成功"""
    logger.info(f"[Chat._is_tool_success] 入参: result类型={type(result).__name__}")
    if isinstance(result, dict):
        # 字典类型：检查 success/exit_code/error 字段
        if 'success' in result:
            return bool(result['success'])
        if 'exit_code' in result:
            return result['exit_code'] == 0
        if 'error' in result:
            return not bool(result['error'])
        return True
    # 字符串类型：检查错误前缀
    result_str = str(result)
    error_prefixes = ("错误:", "文件读取错误:", "工具执行错误:", "Error:", "失败:")
    success = not any(result_str.startswith(p) for p in error_prefixes)
    logger.info(f"[Chat._is_tool_success] 返回: {success}")
    return success


def _format_acceptance_report(round_num: int, acceptance_result: dict) -> str:
    """将验收结果格式化为清晰的验收报告文本，供执行AI参考修复"""
    logger.info(f"[Chat._format_acceptance_report] 入参: round_num={round_num}, passed={acceptance_result.get('passed', 'N/A')}")
    results = acceptance_result.get("results", [])
    failed_items = [r for r in results if not r.get("passed", True)]
    passed_items = [r for r in results if r.get("passed", True)]

    report_lines = [
        f"## 验收报告（第 {round_num} 轮）",
        "",
        "验收结果：未通过",
        "",
    ]

    if failed_items:
        report_lines.append("### 失败项：")
        for idx, item in enumerate(failed_items, 1):
            desc = item.get("criterion", item.get("description", "未知标准"))
            reason = item.get("reason", "未提供原因")
            fix_instruction = item.get("fix_instruction", item.get("suggestion", "无具体修复建议"))
            report_lines.append(f"{idx}. {desc}: 失败")
            report_lines.append(f"   原因: {reason}")
            report_lines.append(f"   修复建议: {fix_instruction}")
            report_lines.append("")

    if passed_items:
        report_lines.append("### 通过项：")
        for idx, item in enumerate(passed_items, 1):
            desc = item.get("criterion", item.get("description", "未知标准"))
            report_lines.append(f"{idx}. {desc}: 通过")
        report_lines.append("")

    report_lines.append("请根据以上验收报告，重点修复失败项中的问题。")
    result = "\n".join(report_lines)
    logger.info(f"[Chat._format_acceptance_report] 返回: {len(result)} chars")
    return result

# 全局打断信号字典：{task_id: True} 表示该任务被请求打断
_abort_signals: dict[int, bool] = {}


def resolve_model_config(db, model_name: str, fallback_cfg):
    """根据模型名称路由到对应的 ApiKey 配置
    
    Args:
        model_name: 要使用的模型名称
        fallback_cfg: 回退配置（当找不到匹配时使用）
    
    Returns:
        (api_key, model, base_url) 三元组
    """
    logger.info(f"[Chat.resolve_model_config] 入参: model_name={model_name}, fallback_cfg_id={fallback_cfg.id if fallback_cfg else None}")
    if not model_name:
        logger.info(f"[Chat.resolve_model_config] 返回: 使用fallback配置 (model_name为空)")
        return fallback_cfg.api_key, fallback_cfg.model_name, fallback_cfg.api_base_url
    
    # 查找包含该模型的配置
    configs = db.query(ApiKeyConfig).all()
    for cfg in configs:
        # 检查 model_list 中是否包含该模型
        if cfg.model_list and model_name in cfg.model_list:
            return cfg.api_key, model_name, cfg.api_base_url
        # 检查 model_name 是否匹配
        if cfg.model_name == model_name:
            return cfg.api_key, model_name, cfg.api_base_url
    
    # 找不到匹配，使用回退配置
    logger.info(f"[Chat.resolve_model_config] 返回: 使用fallback配置 (未找到匹配)")
    return fallback_cfg.api_key, model_name, fallback_cfg.api_base_url


def _save_chat_messages(
    db,
    current_user: User,
    agent_id: Optional[int],
    user_msg: str,
    reply: str,
    intent: str,
    task_id: Optional[int],
    model_name: str,
    config_name: str,
    tool_calls: Optional[list] = None
):
    """保存用户消息和AI回复到数据库（失败不影响主流程）。
    
    后端负责保存对话消息，前端不应重复保存，避免重复记录。
    """
    logger.info(f"[Chat._save_chat_messages] 入参: user_id={current_user.id}, agent_id={agent_id}, intent={intent}, task_id={task_id}, model={model_name}, user_msg={user_msg}, reply={reply if reply else ''}, tool_calls数={len(tool_calls) if tool_calls else 0}")
    try:
        user_message = Message(
            agent_id=agent_id,
            user_id=current_user.id,
            role="user",
            content=user_msg,
            intent=intent if intent else None,
            task_id=task_id,
            model_name=model_name,
            config_name=config_name,
        )
        db.add(user_message)

        ai_message = Message(
            agent_id=agent_id,
            user_id=current_user.id,
            role="assistant",
            content=reply,
            tool_calls=tool_calls if tool_calls else None,
            intent=intent if intent else None,
            task_id=task_id,
            model_name=model_name,
            config_name=config_name,
        )
        db.add(ai_message)
        db.commit()
    except Exception as e:
        logger.warning(f"保存对话消息失败: {e}")
        try:
            db.rollback()
        except Exception:
            pass

# 需要创建任务的意图（复杂操作）
TASK_WORTHY_INTENTS = {"file_operation", "code_generation", "code_review", "project_analysis", "terminal_command", "project_task"}

INTENT_DISPLAY_NAMES = {
    "general_chat": "💬 日常对话",
    "file_operation": "📁 文件操作",
    "code_review": "🔍 代码审查",
    "code_generation": "✨ 代码生成",
    "terminal_command": "💻 终端命令",
    "project_analysis": "📊 项目分析",
    "information_query": "📖 信息查询",
}

@router.get("/configs", response_model=list[ChatConfigItem])
def list_chat_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """返回可用于对话的 Key 配置列表（仅展示 id/name/vendor/model）"""
    logger.info(f"[Chat.list_chat_configs] 入参: user_id={current_user.id}")
    rows = db.query(ApiKeyConfig).order_by(ApiKeyConfig.is_default.desc(), ApiKeyConfig.id).all()
    result = []
    for r in rows:
        if r.api_key:  # 只返回已填写 API Key 的配置
            result.append({
                "id": r.id, "name": r.name,
                "vendor": r.vendor or "openai",
                "model_name": r.model_name,
                "model_list": r.model_list or [r.model_name],
                "is_default": r.is_default,
            })
    logger.info(f"[Chat.list_chat_configs] 返回: {len(result)} 个配置")
    return result

@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """使用指定配置进行对话"""
    logger.info(f"[Chat.chat] 入参: config_id={payload.config_id}, agent_id={payload.agent_id}, model={payload.model}, messages数={len(payload.messages)}")
    # 如果提供了 agent_id，验证智能体存在并获取其配置
    agent = None
    if payload.agent_id:
        agent = db.query(Agent).filter(Agent.id == payload.agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="智能体不存在")
        # 如果智能体绑定了配置，且请求没指定 config_id，用智能体的配置
        if agent.config_id and not payload.config_id:
            payload.config_id = agent.config_id

    # 查找配置
    if not payload.config_id:
        raise HTTPException(status_code=400, detail="未指定配置 ID，且智能体未绑定配置")
    cfg = db.query(ApiKeyConfig).filter(ApiKeyConfig.id == payload.config_id).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="配置不存在")
    if not cfg.api_key:
        raise HTTPException(status_code=400, detail="该配置未填写 API Key")

    # 确定使用哪个模型（如果请求中指定了，则覆盖默认）
    model_to_use = payload.model or cfg.model_name

    # 提取用户消息（用于保存对话记录）
    user_msg = ""
    for m in reversed(payload.messages):
        if m.role == "user":
            user_msg = m.content
            break

    # 从 messages 中提取工作目录和环境信息
    workspace = "."
    env_summary = ""
    for msg in payload.messages:
        if msg.role == "system":
            content = msg.content
            # 提取工作目录
            m = re.search(r"用户的工作目录为[:：]\s*([^\n，。]+)", content)
            if m:
                workspace = m.group(1).strip()
            # 提取环境信息
            m = re.search(r"用户设备环境信息[:：]\n(.*?)\n请根据", content, re.DOTALL)
            if m:
                env_summary = m.group(1).strip()

    # 加载系统设置
    sys_settings = db.query(SystemSettings).first()

    # 尝试创建 Agent Executor
    result = None
    executor = None
    _intent_model = (sys_settings.intent_model if sys_settings and sys_settings.intent_model else None)
    _, _intent_model_name, _ = resolve_model_config(db, _intent_model, cfg)
    try:
        executor = create_chat_agent_executor(
            api_key=cfg.api_key,
            model=model_to_use,
            base_url=cfg.api_base_url or None,
            workspace_root=workspace,
            env_summary=env_summary,
            intent_model=_intent_model_name,
        )
    except Exception as e:
        logger.warning(f"创建Agent失败，将使用fallback模式: {e}")

    if executor and HumanMessage is not None and SystemMessage is not None:
        # 构建 chat_history 和 input
        role_map = {
            "system": SystemMessage,
            "user": HumanMessage,
            "assistant": AIMessage,
        }

        # 找到最后一个 user 消息作为 input
        last_user_idx = -1
        for i, m in enumerate(payload.messages):
            if m.role == "user":
                last_user_idx = i

        if last_user_idx == -1:
            raise HTTPException(status_code=400, detail="消息中缺少用户输入")

        chat_history = []
        user_message = ""
        for i, m in enumerate(payload.messages):
            if m.role == "system":
                continue
            if i == last_user_idx:
                user_message = m.content
            else:
                cls = role_map.get(m.role, HumanMessage)
                chat_history.append(cls(content=m.content))

        try:
            result = executor.invoke({
                "input": user_message,
                "chat_history": chat_history,
            })
        except Exception as e:
            logger.warning(f"Agent执行失败，将使用fallback模式: {e}")
            result = None

    if result:
        # 提取工具调用轨迹
        tool_calls = []
        for step in result.get("intermediate_steps", []):
            action, observation = step
            tool_calls.append(ToolCallTrace(
                tool_name=action.tool,
                parameters=action.tool_input if isinstance(action.tool_input, dict) else {"input": action.tool_input},
                result=str(observation)[:2000],
                success="error" not in str(observation).lower()
            ))

        reply = _strip_context_summary(result.get("output", ""))
        intent = result.get("intent", "")
        intent_display = INTENT_DISPLAY_NAMES.get(intent, f"🎯 {intent}")
        
        # === 自动创建任务记录 ===
        task_record = None
        if intent in TASK_WORTHY_INTENTS:
            try:
                # 从用户消息中提取任务描述
                user_msg = ""
                for m in reversed(payload.messages):
                    if m.role == "user":
                        user_msg = m.content
                        break
                
                task_name = user_msg[:50] + ("..." if len(user_msg) > 50 else "")
                
                # 判断任务状态
                all_success = all(tc.success for tc in tool_calls)
                task_status = "completed" if all_success else "failed"
                
                # 构建任务结果摘要
                tool_summary = "; ".join([
                    f"{tc.tool_name}({'✓' if tc.success else '✗'})" 
                    for tc in tool_calls
                ])
                
                task_record = Task(
                    name=f"[AI对话] {task_name}",
                    description=f"意图: {intent_display}\n工具调用: {tool_summary}",
                    ai_reply=reply,
                    status=task_status,
                    priority=1,  # medium
                    intent_tag=intent,  # 从意图识别结果中获取
                    agent_id=agent.id if agent else None,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.add(task_record)
                db.commit()
                db.refresh(task_record)
            except Exception as e:
                logger.warning(f"创建任务记录失败: {e}")
                # 不影响正常对话返回
        
        if not reply:
            reply = "Agent执行完成，但未返回输出内容"

        # 保存对话消息到数据库
        _save_chat_messages(
            db=db,
            current_user=current_user,
            agent_id=payload.agent_id,
            user_msg=user_msg,
            reply=reply,
            intent=intent,
            task_id=task_record.id if task_record else None,
            model_name=model_to_use,
            config_name=cfg.name,
            tool_calls=[tc.model_dump() if hasattr(tc, "model_dump") else dict(tc) for tc in tool_calls] if tool_calls else None,
        )

        return ChatResponse(
            reply=reply,
            model_name=model_to_use,
            vendor=cfg.vendor or "openai",
            config_name=cfg.name,
            tool_calls=tool_calls,
            intent=intent,
            intent_display_name=intent_display,
            task_id=task_record.id if task_record else None,
        )

    # Fallback: 使用原有的简单 invoke 方式
    # 获取 LLM 实例
    llm_instance = get_llm_for_config(cfg.id)
    if llm_instance is None or payload.model:
        # 尝试即时构建（指定了 model 时也重新构建）
        from services.llm_service import _build_llm
        llm_instance = _build_llm(model_to_use, cfg.api_key, cfg.api_base_url or "")
        if llm_instance is None:
            raise HTTPException(status_code=500, detail="无法初始化语言模型")

    # 构建 LangChain 消息列表
    lc_messages = _build_lc_messages(payload.messages)

    # [日志] Fallback 模式 LLM 调用
    logger.info(f"[LLM Request] Fallback mode, messages ({len(lc_messages)} msgs):")
    for _mi, _m in enumerate(lc_messages):
        _role = _m.get('role', 'unknown') if isinstance(_m, dict) else getattr(_m, '__class__', type(_m)).__name__
        _cont = (_m.get('content', '') if isinstance(_m, dict) else str(getattr(_m, 'content', '')))[:200]
        logger.info(f"  [{_mi}] {_role}: {_cont}")

    try:
        response = llm_instance.invoke(lc_messages)
        reply = response.content if hasattr(response, 'content') else str(response)
        reply = _strip_context_summary(reply.strip())
        logger.info(f"[LLM Response] Fallback mode, content: {reply}")
    except Exception as e:
        logger.error(f"[LLM Error] Fallback mode, error: {e}")
        raise HTTPException(status_code=502, detail=f"模型调用失败: {str(e)}")

    # 保存对话消息到数据库
    _save_chat_messages(
        db=db,
        current_user=current_user,
        agent_id=payload.agent_id,
        user_msg=user_msg,
        reply=reply,
        intent="general_chat",
        task_id=None,
        model_name=model_to_use,
        config_name=cfg.name,
        tool_calls=None,
    )

    return ChatResponse(
        reply=reply,
        model_name=model_to_use,
        vendor=cfg.vendor or "openai",
        config_name=cfg.name,
        tool_calls=[],
        intent="general_chat",
        intent_display_name=INTENT_DISPLAY_NAMES.get("general_chat", "💬 日常对话"),
        task_id=None,
    )


def _build_lc_messages(messages: list) -> list:
    """将 API 消息转换为 LangChain 消息对象"""
    logger.info(f"[Chat._build_lc_messages] 入参: messages数={len(messages)}")
    if HumanMessage is None:
        # fallback: 使用 dict 格式（兼容 openai 风格）
        return [{"role": m.role, "content": m.content} for m in messages]

    role_map = {
        "system": SystemMessage,
        "user": HumanMessage,
        "assistant": AIMessage,
    }
    result = []
    for m in messages:
        cls = role_map.get(m.role, HumanMessage)
        result.append(cls(content=m.content))
    logger.info(f"[Chat._build_lc_messages] 返回: {len(result)} 条消息")
    return result


@router.post("/abort/{task_id}")
def abort_chat_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """打断正在执行的AI对话任务"""
    logger.info(f"[Chat.abort_chat_task] 入参: task_id={task_id}")
    _abort_signals[task_id] = True
    # 更新任务状态为 cancelled
    task = db.query(Task).filter(Task.id == task_id).first()
    if task and task.status == "in_progress":
        task.status = "cancelled"
        task.progress_message = "用户手动打断"
        db.commit()
    logger.info(f"[Chat.abort_chat_task] 返回: 任务 #{task_id} 已请求打断")
    return {"success": True, "message": f"任务 #{task_id} 已请求打断"}


@router.post("/stream")
async def chat_stream(
    request: Request,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """流式对话端点 - 实时推送意图识别、任务创建、工具调用过程"""
    logger.info(f"[Chat.chat_stream] 入参: config_id={payload.config_id}, agent_id={payload.agent_id}, model={payload.model}, messages数={len(payload.messages)}")

    # 1. 查找配置
    cfg = None
    agent = None

    if payload.agent_id:
        agent = db.query(Agent).filter(Agent.id == payload.agent_id).first()
        if agent and agent.config_id:
            cfg = db.query(ApiKeyConfig).filter(ApiKeyConfig.id == agent.config_id).first()

    if not cfg and payload.config_id:
        cfg = db.query(ApiKeyConfig).filter(ApiKeyConfig.id == payload.config_id).first()

    if not cfg:
        cfg = db.query(ApiKeyConfig).filter(ApiKeyConfig.is_default == True).first()

    if not cfg or not cfg.api_key:
        async def error_stream():
            yield f"data: {json.dumps({'type': 'error', 'message': '未找到可用的 API Key 配置'})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    model_to_use = payload.model or cfg.model_name

    # 提取工作目录和环境信息
    workspace = "."
    env_summary = ""
    for msg in payload.messages:
        if msg.role == "system":
            content = msg.content
            m = re.search(r"用户的工作目录为[:：]\s*([^\n，。]+)", content)
            if m:
                workspace = m.group(1).strip()
            m = re.search(r"用户设备环境信息[:：]\n(.*?)\n请根据", content, re.DOTALL)
            if m:
                env_summary = m.group(1).strip()

    # 获取用户消息
    user_msg = ""
    for m in reversed(payload.messages):
        if m.role == "user":
            user_msg = m.content
            break

    TOOL_DISPLAY_NAMES = {
        "file_search": "搜索文件",
        "file_read": "查看文件",
        "file_create": "创建文件",
        "file_update": "修改文件",
        "file_delete": "删除文件",
        "terminal_execute": "执行命令",
        "file_find": "查找文件",
    }

    def generate_tool_description(tool_name: str, tool_args: dict) -> str:
        args = tool_args if isinstance(tool_args, dict) else {}
        if tool_name == "file_read":
            return f"查看文件: {args.get('path', '')}"
        elif tool_name == "file_search":
            return f"搜索文件: {args.get('query', '')}"
        elif tool_name == "file_create":
            return f"创建文件: {args.get('path', '')}"
        elif tool_name == "file_update":
            return f"修改文件: {args.get('path', '')}"
        elif tool_name == "file_delete":
            return f"删除文件: {args.get('path', '')}"
        elif tool_name == "terminal_execute":
            cmd = args.get('command', '')
            return f"执行命令: {cmd[:50]}{'...' if len(cmd) > 50 else ''}"
        elif tool_name == "file_find":
            return f"查找文件: {args.get('pattern', '')}"
        return tool_name

    ai_pool = request.app.state.ai_thread_pool
    loop = asyncio.get_event_loop()

    async def event_stream():
        def send_event(event_type: str, data: dict):
            payload_str = json.dumps({**data, "type": event_type}, ensure_ascii=False)
            return f"data: {payload_str}\n\n"

        # === 第1步：创建 Agent ===
        yield send_event("status", {"message": "正在初始化 AI 助手..."})

        # === 检查 confirmed_task_id ===
        confirmed_task_id = None
        for msg in payload.messages:
            if msg.role == "system" and "confirmed_task_id:" in msg.content:
                m = re.search(r"confirmed_task_id:\s*(\d+)", msg.content)
                if m:
                    confirmed_task_id = int(m.group(1))
        
        task_id = None
        task_record = None
        intent = None
        intent_display = ""
        plan_steps_db = []
        acceptance_criteria = None

        # 从 payload 提取用户消息（避免局部变量未绑定问题）
        user_msg = ""
        for _m in reversed(payload.messages):
            if _m.role == "user":
                user_msg = _m.content
                break

        logger.info(f"[Chat] 用户消息: {user_msg}")

        if confirmed_task_id:
            task_record = db.query(Task).filter(Task.id == confirmed_task_id).first()
            if not task_record:
                yield send_event("error", {"message": f"任务 #{confirmed_task_id} 不存在"})
                return
            
            task_id = confirmed_task_id
            acceptance_criteria = task_record.acceptance_criteria if task_record else None
            intent = task_record.intent_tag or "project_task"
            intent_display = INTENT_DISPLAY_NAMES.get(intent, f"🎯 {intent}")
            user_msg = task_record.description or ""
            if "用户请求:" in user_msg:
                user_msg = user_msg.split("用户请求:")[-1].strip()
            
            yield send_event("status", {"message": "正在恢复任务执行..."})
            yield send_event("intent", {
                "intent": intent,
                "display_name": intent_display,
                "message": f"恢复意图: {intent_display}"
            })
            yield send_event("task_created", {"task_id": task_id, "message": f"任务 #{task_id} 继续执行"})

        from services.chat_agent import (
            classify_intent_llm,
            IntentType, INTENT_TOOL_MAP, INTENT_PROMPT_SUFFIX,
            create_mcp_tools, ContextManager
        )

        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                api_key=cfg.api_key,
                model=model_to_use,
                base_url=cfg.api_base_url or None,
                temperature=0.7,
                max_tokens=4096,
                timeout=60,
            )
        except Exception as e:
            yield send_event("error", {"message": f"模型初始化失败: {e}"})
            return

        # 加载系统设置
        sys_settings = db.query(SystemSettings).first()

        if not confirmed_task_id:
            # === 第2步：意图识别 ===
            yield send_event("status", {"message": "正在分析用户意图..."})

            # 意图识别 - 完全使用 LLM
            from services.chat_agent import create_intent_llm
            _intent_model = (sys_settings.intent_model if sys_settings and sys_settings.intent_model else "")
            _intent_api_key, _intent_model_name, _intent_base_url = resolve_model_config(db, _intent_model, cfg)
            intent_llm = create_intent_llm(_intent_api_key, _intent_model_name, _intent_base_url or None)
            if intent_llm:
                intent = await loop.run_in_executor(ai_pool, classify_intent_llm, intent_llm, user_msg)
            else:
                intent = await loop.run_in_executor(ai_pool, classify_intent_llm, llm, user_msg)

            intent_display = INTENT_DISPLAY_NAMES.get(intent, f"🎯 {intent}")
            logger.info(f"[Intent] 识别结果: {intent}, 显示名: {intent_display}")
            yield send_event("intent", {
                "intent": intent,
                "display_name": intent_display,
                "message": f"识别意图: {intent_display}"
            })

        if not confirmed_task_id:
            # === 第3步：意图识别后，仅复杂意图创建任务 ===
            task_id = None
            task_record = None
            if intent in TASK_WORTHY_INTENTS:
                task_name = user_msg[:50] + ("..." if len(user_msg) > 50 else "")
                try:
                    task_record = Task(
                        name=f"[AI对话] {task_name}",
                        description=f"意图: {intent_display}\n用户请求: {user_msg[:200]}",
                        status="in_progress",
                        priority=1,
                        intent_tag=intent,
                        progress=10,
                        progress_message="意图识别完成，准备执行",
                        agent_id=agent.id if agent else None,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    db.add(task_record)
                    db.commit()
                    db.refresh(task_record)
                    task_id = task_record.id
                    logger.info(f"[Task] 任务已创建: id={task_id}, intent={intent}")
                    yield send_event("task_created", {"task_id": task_id, "message": f"任务 #{task_id} 已创建"})
                except Exception as e:
                    logger.warning(f"创建任务失败: {e}")

        if not confirmed_task_id:
            # === 计划生成阶段 ===
            plan_steps_db = []
            if intent in TASK_WORTHY_INTENTS and task_id is not None:
                try:
                    yield send_event("status", {"message": "正在生成执行计划..."})
                    _tools_for_plan = create_mcp_tools(workspace)
                    _allowed = INTENT_TOOL_MAP.get(intent)
                    if _allowed is not None:
                        _filtered_for_plan = [t for t in _tools_for_plan if t.name in _allowed]
                    else:
                        _filtered_for_plan = _tools_for_plan
                    _plan_model = (sys_settings.plan_model if sys_settings and sys_settings.plan_model else "")
                    _plan_api_key, _plan_model_name, _plan_base_url = resolve_model_config(db, _plan_model, cfg)
                    plan_result = await loop.run_in_executor(
                        ai_pool,
                        partial(generate_execution_plan,
                            api_key=_plan_api_key, model=_plan_model_name, base_url=_plan_base_url or None,
                            user_msg=user_msg, intent=intent,
                            available_tools=[t.name for t in _filtered_for_plan]
                        )
                    )
                    logger.info(f"[Plan] 执行计划生成: {len(plan_result.get('steps', []))} 步")
                    for s in plan_result.get('steps', []):
                        logger.info(f"[Plan]   - {s.get('name', '')}: {s.get('description', '')}")
                    for idx, step_data in enumerate(plan_result.get("steps", []), start=1):
                        ws = WorkflowStep(
                            task_id=task_id,
                            name=step_data.get("name", f"步骤 {idx}"),
                            description=step_data.get("description", ""),
                            status="pending",
                            order=idx,
                        )
                        db.add(ws)
                        plan_steps_db.append(ws)
                    db.commit()
                    for ws in plan_steps_db:
                        db.refresh(ws)
                    if plan_steps_db:
                        plan_steps_db[0].status = "running"
                        db.commit()
                    yield send_event("plan_generated", {
                        "task_id": task_id,
                        "steps": [
                            {"id": ws.id, "order": ws.order, "name": ws.name,
                             "description": ws.description, "status": ws.status}
                            for ws in plan_steps_db
                        ],
                        "total": len(plan_steps_db),
                        "message": f"已生成执行计划，共 {len(plan_steps_db)} 步"
                    })
                except Exception as e:
                    logger.error(f"计划生成失败，跳过: {e}")

            # === 验收标准生成阶段（两步式第一步）===
            if intent in TASK_WORTHY_INTENTS and task_id is not None:
                try:
                    from services.acceptance_service import generate_acceptance_criteria as gen_criteria
                    yield send_event("status", {"message": "正在生成验收标准..."})
                    _tools_for_criteria = create_mcp_tools(workspace)
                    _allowed_c = INTENT_TOOL_MAP.get(intent)
                    if _allowed_c is not None:
                        _filtered_for_criteria = [t for t in _tools_for_criteria if t.name in _allowed_c]
                    else:
                        _filtered_for_criteria = _tools_for_criteria
                    _acceptance_model = (sys_settings.acceptance_model if sys_settings and sys_settings.acceptance_model else "")
                    _acc_api_key, _acc_model_name, _acc_base_url = resolve_model_config(db, _acceptance_model, cfg)
                    criteria_result = await loop.run_in_executor(
                        ai_pool,
                        partial(gen_criteria,
                            api_key=_acc_api_key, model=_acc_model_name,
                            base_url=_acc_base_url or None,
                            user_msg=user_msg, intent=intent,
                            available_tools=[t.name for t in _filtered_for_criteria]
                        )
                    )
                    criteria_list = criteria_result.get("criteria", [])
                    logger.info(f"[Acceptance] 验收标准生成: {len(criteria_list)} 条")
                    for c in criteria_list:
                        desc = c.get('description', c) if isinstance(c, dict) else str(c)
                        logger.info(f"[Acceptance]   - {str(desc)}")

                    # 存入 Task
                    task_obj = db.query(Task).filter(Task.id == task_id).first()
                    if task_obj:
                        task_obj.acceptance_criteria = criteria_list
                        db.commit()
                    
                    # 发送验收标准给前端
                    yield send_event("acceptance_criteria_generated", {
                        "task_id": task_id,
                        "criteria": criteria_list,
                        "message": "请确认验收标准后开始执行"
                    })
                    
                    # 发送一条提示性的 reply 告知用户
                    yield send_event("reply", {
                        "reply": f"已为您生成 {len(criteria_list)} 条验收标准，请确认或编辑后点击「确认执行」开始任务。",
                        "task_id": task_id,
                        "intent": intent,
                        "done": True
                    })
                    return  # 第一步结束，不进入工具调用循环
                except Exception as e:
                    logger.error(f"验收标准生成失败，跳过验收机制: {e}")
                    # 失败则继续走原有流程（直接执行）

        # === 第4步：根据意图路由 ===
        if intent in (IntentType.GENERAL_CHAT, IntentType.INFORMATION_QUERY):
            yield send_event("status", {"message": "AI 正在思考回复..."})
            try:
                from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

                messages = []
                role_map = {"system": SystemMessage, "user": HumanMessage, "assistant": AIMessage}
                for m in payload.messages:
                    cls = role_map.get(m.role, HumanMessage)
                    messages.append(cls(content=m.content))

                # [日志] 简单对话 LLM 调用
                logger.info(f"[LLM Request] General chat, messages ({len(messages)} msgs):")
                for _mi, _m in enumerate(messages):
                    _role = _m.__class__.__name__
                    _cont = str(_m.content)[:200] if _m.content else '(empty)'
                    logger.info(f"  [{_mi}] {_role}: {_cont}")

                response = await loop.run_in_executor(ai_pool, llm.invoke, messages)
                reply = _strip_context_summary(response.content or "")
                logger.info(f"[LLM Response] General chat, content: {reply}")

                if task_record:
                    try:
                        task_record.status = "completed"
                        task_record.progress = 100
                        task_record.progress_message = "对话完成"
                        task_record.ai_reply = reply
                        db.commit()
                    except Exception:
                        pass

                yield send_event("reply", {
                    "reply": reply,
                    "model_name": model_to_use,
                    "vendor": cfg.vendor or "openai",
                    "config_name": cfg.name,
                    "tool_calls": [],
                    "intent": intent,
                    "task_id": task_id,
                })
                # 保存对话消息到数据库
                _save_chat_messages(
                    db=db,
                    current_user=current_user,
                    agent_id=payload.agent_id,
                    user_msg=user_msg,
                    reply=reply,
                    intent=intent,
                    task_id=task_id,
                    model_name=model_to_use,
                    config_name=cfg.name,
                    tool_calls=None,
                )
            except Exception as e:
                yield send_event("error", {"message": f"对话失败: {e}"})
            if task_id is not None:
                _abort_signals.pop(task_id, None)
            return

        # === 第5步：需要工具调用的意图 ===
        yield send_event("status", {"message": "正在准备工具..."})

        try:
            from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
        except ImportError as e:
            yield send_event("error", {"message": f"依赖导入失败: {e}"})
            if task_id is not None:
                _abort_signals.pop(task_id, None)
            return

        tools = create_mcp_tools(workspace)

        allowed_tools = INTENT_TOOL_MAP.get(intent)
        if allowed_tools is not None:
            filtered_tools = [t for t in tools if t.name in allowed_tools]
        else:
            filtered_tools = tools

        tool_map = {t.name: t for t in filtered_tools}

        try:
            llm_with_tools = llm.bind_tools(filtered_tools) if filtered_tools else llm
        except Exception:
            llm_with_tools = llm

        system_prompt = f"""你是一个强大的AI助手，可以通过工具来帮助用户完成各种任务。
你拥有以下工具能力：{', '.join([t.name for t in filtered_tools])}
当用户要求你操作文件、执行命令或查看代码时，请主动使用这些工具来完成任务。
{INTENT_PROMPT_SUFFIX.get(intent, '')}

## 执行规范
1. 如果有执行计划，严格按照计划的顺序逐步完成每个步骤
2. 每个步骤完成后，自动开始下一步，不要停下来等待用户确认
3. 所有步骤完成后，给出完整的执行总结
4. 如果某个步骤执行失败，尝试换一种方式解决，不要跳过"""

        if env_summary:
            system_prompt += f"\n当前环境信息：\n{env_summary}"

        # === 加载相关 Skill ===
        skill_contents = load_relevant_skills(db, payload.agent_id, workspace, user_msg)
        if skill_contents:
            skills_text = "\n\n".join(skill_contents)
            system_prompt += f"\n\n--- 相关技能经验 ---\n{skills_text}"

        # 注入执行计划到系统提示
        if plan_steps_db:
            plan_text = "\n\n## 执行计划（请严格按照此计划逐步执行）\n"
            for ws in plan_steps_db:
                status_icon = {"pending": "⬜", "running": "▶️", "completed": "✅"}.get(ws.status, "⬜")
                plan_text += f"{status_icon} 第{ws.order}步: {ws.name} - {ws.description}\n"
            plan_text += "\n请按顺序执行上述计划，每完成一步才进入下一步。当前需要执行的是第一个未完成的步骤。"
            system_prompt += plan_text

        current_messages = [SystemMessage(content=system_prompt)]

        role_map = {"user": HumanMessage, "assistant": AIMessage}
        for m in payload.messages:
            if m.role != "system":
                cls = role_map.get(m.role, HumanMessage)
                current_messages.append(cls(content=m.content))

        context_manager = ContextManager(max_tokens=8000)

        all_tool_calls = []
        step_count = 0
        current_plan_step = 0
        max_iterations = (sys_settings.max_tool_iterations if sys_settings and hasattr(sys_settings, 'max_tool_iterations') and sys_settings.max_tool_iterations else 30)

        # === 工具调用循环 ===
        for i in range(max_iterations):
            step_count = i + 1

            # 检查打断信号
            if task_id and _abort_signals.get(task_id):
                _abort_signals.pop(task_id, None)
                yield send_event("status", {"message": "任务已被用户打断"})
                reply = f"任务已被打断。已完成 {step_count} 步工具调用。"
                if task_record:
                    task_record.status = "cancelled"
                    task_record.progress_message = "用户手动打断"
                    task_record.ai_reply = reply
                    db.commit()

                # 标记剩余步骤为完成
                if plan_steps_db:
                    for ws in plan_steps_db:
                        if ws.status in ("pending", "running"):
                            ws.status = "completed"
                    db.commit()

                yield send_event("reply", {
                    "reply": reply,
                    "model_name": model_to_use,
                    "tool_calls": all_tool_calls,
                    "task_id": task_id,
                    "aborted": True
                })
                return

            if context_manager.should_compress(current_messages):
                yield send_event("status", {"message": "上下文接近上限，正在压缩..."})
                current_messages = context_manager.compress_context(current_messages)

            progress = min(10 + (i * 80 // max_iterations), 90)
            if task_record:
                try:
                    task_record.progress = progress
                    task_record.progress_message = f"执行第 {step_count} 步"
                    db.commit()
                except Exception:
                    pass

            yield send_event("status", {"message": f"AI 正在思考（第 {step_count} 步）..."})

            # [日志] 工具循环 LLM 调用前
            logger.info(f"[LLM Request] Round {step_count}, messages ({len(current_messages)} msgs):")
            for _mi, _m in enumerate(current_messages):
                _role = _m.__class__.__name__
                _cont = str(_m.content)[:200] if _m.content else '(empty)'
                logger.info(f"  [{_mi}] {_role}: {_cont}")

            try:
                llm_start = time.time()
                response = await loop.run_in_executor(ai_pool, llm_with_tools.invoke, current_messages)
                llm_elapsed = time.time() - llm_start
            except Exception as e:
                logger.error(f"[LLM Error] Round {step_count}, error: {e}")
                yield send_event("error", {"message": f"模型调用失败: {e}"})
                break

            # [日志] 工具循环 LLM 调用后
            _resp_content = str(response.content)[:200] if response.content else '(empty)'
            _tc_summary = 'none'
            if hasattr(response, 'tool_calls') and response.tool_calls:
                _tc_summary = ', '.join([f"{tc.get('name','?')}({str(tc.get('args',''))[:80]})" for tc in response.tool_calls])
            logger.info(f"[LLM Response] Round {step_count}, elapsed: {llm_elapsed:.1f}s, content: {_resp_content}, tool_calls: {_tc_summary}")

            tool_calls_raw = getattr(response, "tool_calls", None)
            if not tool_calls_raw:
                reply = _strip_context_summary(response.content or "")

                # === 验收阶段 ===
                # 判断是否有有效的验收标准：None、空列表、空字符串均视为无验收标准
                _has_acceptance = bool(confirmed_task_id and acceptance_criteria and
                                      (isinstance(acceptance_criteria, list) and len(acceptance_criteria) > 0 or
                                       isinstance(acceptance_criteria, str) and acceptance_criteria.strip()))
                if _has_acceptance:
                    max_acceptance_rounds = (sys_settings.max_acceptance_rounds if sys_settings else 3) or 3
                    _limit = max_acceptance_rounds if max_acceptance_rounds > 0 else 999999

                    for round_num in range(_limit):
                        # 更新验收次数
                        task_obj = db.query(Task).filter(Task.id == task_id).first()
                        if task_obj:
                            task_obj.acceptance_attempts = round_num + 1
                            task_obj.acceptance_status = "in_review"
                            db.commit()

                        yield send_event("status", {"message": f"验收工程师正在检查（第{round_num+1}轮）..."})

                        acceptance_result = await loop.run_in_executor(
                            ai_pool,
                            partial(run_acceptance_check,
                                api_key=cfg.api_key, model=model_to_use,
                                base_url=cfg.api_base_url or None,
                                criteria=acceptance_criteria,
                                task_result=reply,
                                workspace=workspace,
                                tool_calls_log=all_tool_calls
                            )
                        )

                        yield send_event("acceptance_result", {
                            "task_id": task_id,
                            "round": round_num + 1,
                            "passed": acceptance_result.get("passed", True),
                            "results": acceptance_result.get("results", []),
                            "max_rounds": max_acceptance_rounds if max_acceptance_rounds > 0 else 0
                        })

                        if acceptance_result.get("passed", True):
                            # 验收通过
                            logger.info(f"[Acceptance] 第 {round_num+1} 轮验收: 通过")
                            if task_obj:
                                task_obj.acceptance_status = "passed"
                                db.commit()
                            break

                        # 验收未通过
                        logger.info(f"[Acceptance] 第 {round_num+1} 轮验收: 未通过")
                        for item in acceptance_result.get("results", []):
                            status = item.get('status', 'passed' if item.get('passed', True) else 'failed')
                            reason = str(item.get('reason', ''))[:100]
                            logger.info(f"[Acceptance]   - [{status}] {reason}")

                        # 验收未通过，进行修复
                        if round_num < _limit - 1:
                            yield send_event("status", {"message": f"验收未通过，正在修复（第{round_num+1}轮）..."})

                            # 格式化验收报告，作为上下文发送给执行AI
                            acceptance_report = _format_acceptance_report(round_num + 1, acceptance_result)

                            # 重建精简的修复上下文（避免消息链膨胀）
                            fix_messages = [
                                SystemMessage(content=system_prompt + "\n\n## 修复模式\n你现在处于修复模式。验收工程师发现了问题，请根据验收报告修复。"),
                                HumanMessage(content=f"原始任务: {user_msg}"),
                                HumanMessage(content=f"已执行的操作摘要:\n" + "\n".join([
                                    f"- [{'成功' if tc['success'] else '失败'}] {tc['tool_name']}: {tc.get('description', '')[:100]}"
                                    for tc in all_tool_calls
                                ])),
                                HumanMessage(content=acceptance_report),
                                HumanMessage(content="请根据验收报告中的失败项进行针对性修复，确保所有验收标准通过。"),
                            ]

                            # 简化的修复循环（最多 max_iterations 次工具调用）
                            for fix_i in range(max_iterations):
                                logger.info(f"[LLM Request] Acceptance fix {round_num+1}-{fix_i+1}, messages ({len(fix_messages)} msgs)")
                                response = await loop.run_in_executor(ai_pool, llm_with_tools.invoke, fix_messages)

                                # 清理 response content
                                resp_content = response.content or ""
                                resp_content = _strip_context_summary(resp_content)
                                _fix_tc = ', '.join([tc.get('name','?') for tc in (response.tool_calls or [])]) or 'none'
                                logger.info(f"[LLM Response] Acceptance fix {round_num+1}-{fix_i+1}, content: {resp_content}, tool_calls: {_fix_tc}")

                                if not response.tool_calls:
                                    # 修复完成，收集结果
                                    reply = resp_content
                                    break

                                # 执行工具调用（复用现有逻辑）
                                fix_messages.append(response)
                                for tool_call in response.tool_calls:
                                    tool_name = tool_call.get("name", "")
                                    tool_args = tool_call.get("args", {})
                                    tool_id = tool_call.get("id", "")

                                    tool_fn = tool_map.get(tool_name)
                                    if tool_fn:
                                        try:
                                            result = await loop.run_in_executor(ai_pool, tool_fn.invoke, tool_args)
                                        except Exception as e:
                                            result = f"工具执行错误: {e}"
                                    else:
                                        result = f"工具 {tool_name} 未找到"

                                    logger.info(f"[Tool Result] {tool_name}: {str(result)}")
                                    fix_messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))

                                    result_str = str(result)
                                    yield send_event("tool_end", {
                                        "tool": tool_name,
                                        "result": result_str[:500],
                                        "success": _is_tool_success(result)
                                    })
                        else:
                            # 达到最大验收轮数
                            if task_obj:
                                task_obj.acceptance_status = "failed"
                                db.commit()
                            yield send_event("status", {"message": "已达最大验收轮数，任务标记为验收失败"})
                elif confirmed_task_id and not _has_acceptance:
                    # 无验收标准，跳过验收流程，直接完成任务
                    logger.info(f"[Acceptance] Task #{task_id} 无验收标准，跳过验收流程")
                    yield send_event("status", {"message": "无验收标准，直接完成任务"})

                all_success = all(tc.get("success", True) for tc in all_tool_calls)
                if task_record:
                    try:
                        task_record.status = "completed" if all_success else "failed"
                        task_record.progress = 100
                        task_record.progress_message = "任务完成"
                        task_record.description = f"意图: {intent}\n工具调用: {len(all_tool_calls)}次"
                        task_record.ai_reply = reply
                        db.commit()
                    except Exception:
                        pass

                # 标记剩余步骤为完成
                if plan_steps_db:
                    for ws in plan_steps_db:
                        if ws.status in ("pending", "running"):
                            ws.status = "completed"
                    db.commit()

                logger.info(f"[Reply] 最终回复: {reply if reply else '(empty)'}")
                yield send_event("reply", {
                    "reply": reply,
                    "model_name": model_to_use,
                    "vendor": cfg.vendor or "openai",
                    "config_name": cfg.name,
                    "tool_calls": all_tool_calls,
                    "intent": intent,
                    "task_id": task_id,
                })
                # 保存对话消息到数据库
                _save_chat_messages(
                    db=db,
                    current_user=current_user,
                    agent_id=payload.agent_id,
                    user_msg=user_msg,
                    reply=reply,
                    intent=intent,
                    task_id=task_id,
                    model_name=model_to_use,
                    config_name=cfg.name,
                    tool_calls=all_tool_calls if all_tool_calls else None,
                )
                if task_id is not None:
                    _abort_signals.pop(task_id, None)
                return

            # 在追加 response 到消息链之前，清理 content 中可能包含的工具调用标记
            cleaned_content = _strip_context_summary(response.content or "")
            cleaned_response = AIMessage(
                content=cleaned_content,
                tool_calls=response.tool_calls if hasattr(response, 'tool_calls') else [],
                additional_kwargs=response.additional_kwargs if hasattr(response, 'additional_kwargs') else {},
            )
            current_messages.append(cleaned_response)

            for tc in tool_calls_raw:
                tool_name = tc.get("name") or tc.get("function", {}).get("name")
                tool_args = tc.get("args") or tc.get("function", {}).get("arguments", {})
                tool_call_id = tc.get("id", "")

                description = generate_tool_description(tool_name, tool_args)

                yield send_event("tool_start", {
                    "tool_name": tool_name,
                    "display_name": TOOL_DISPLAY_NAMES.get(tool_name, tool_name),
                    "description": description,
                    "parameters": tool_args if isinstance(tool_args, dict) else {"input": tool_args},
                    "step": step_count,
                    "message": f"正在执行: {tool_name}",
                })

                logger.info(f"[Tool Call] Round {step_count}, tool: {tool_name}, args: {str(tool_args)}")
                tool_start = time.time()

                tool_fn = tool_map.get(tool_name)
                if tool_fn:
                    try:
                        result = await loop.run_in_executor(ai_pool, tool_fn.invoke, tool_args)
                        result_str = str(result)
                        success = _is_tool_success(result)
                    except Exception as e:
                        result = f"工具执行错误: {e}"
                        success = False
                else:
                    result = f"工具 {tool_name} 未找到"
                    success = False

                tool_elapsed = time.time() - tool_start
                logger.info(f"[Tool Result] {tool_name}: {str(result)} (elapsed: {tool_elapsed:.1f}s, success: {success})")

                tool_call_info = {
                    "tool_name": tool_name,
                    "display_name": TOOL_DISPLAY_NAMES.get(tool_name, tool_name),
                    "description": description,
                    "parameters": tool_args if isinstance(tool_args, dict) else {"input": tool_args},
                    "result": str(result)[:2000],
                    "success": success,
                    "step": step_count,
                }
                all_tool_calls.append(tool_call_info)

                yield send_event("tool_end", {
                    **tool_call_info,
                    "message": f"{tool_name} {'✓' if success else '✗'}",
                })

                # 更新待办清单步骤状态
                current_plan_step += 1
                if plan_steps_db and current_plan_step <= len(plan_steps_db):
                    step_to_update = plan_steps_db[current_plan_step - 1]
                    step_to_update.status = "completed"
                    db.commit()
                    yield send_event("step_completed", {
                        "task_id": task_id,
                        "step_order": current_plan_step,
                        "status": "completed",
                        "message": f"步骤 {current_plan_step} 完成: {step_to_update.name}"
                    })
                    if current_plan_step < len(plan_steps_db):
                        next_step = plan_steps_db[current_plan_step]
                        next_step.status = "running"
                        db.commit()

                current_messages.append(
                    ToolMessage(content=str(result), tool_call_id=tool_call_id)
                )

            # 注入进度提示，引导 AI 执行下一步
            if plan_steps_db and current_plan_step < len(plan_steps_db):
                next_step = plan_steps_db[current_plan_step]
                progress_hint = HumanMessage(content=f"[系统提示] 上一步已完成。请继续执行下一步：{next_step.name} - {next_step.description}")
                current_messages.append(progress_hint)

        # 达到最大迭代
        yield send_event("status", {"message": "正在总结执行结果..."})
        try:
            summary_msg = HumanMessage(content="请根据以上所有工具调用的结果，给用户一个完整的总结回复。不要再调用任何工具。")
            current_messages.append(summary_msg)
            logger.info(f"[LLM Request] Summary round, messages ({len(current_messages)} msgs)")
            final_response = await loop.run_in_executor(ai_pool, llm.invoke, current_messages)
            reply = _strip_context_summary(final_response.content or "任务执行完成")
            logger.info(f"[LLM Response] Summary round, content: {reply}")
        except Exception:
            reply = "工具调用结果摘要：\n" + "\n".join([
                f"[{tc['tool_name']}] {'成功' if tc['success'] else '失败'}" for tc in all_tool_calls
            ])

        # === 验收阶段 ===
        # 判断是否有有效的验收标准：None、空列表、空字符串均视为无验收标准
        _has_acceptance_final = bool(confirmed_task_id and acceptance_criteria and
                                    (isinstance(acceptance_criteria, list) and len(acceptance_criteria) > 0 or
                                     isinstance(acceptance_criteria, str) and acceptance_criteria.strip()))
        if _has_acceptance_final:
            max_acceptance_rounds = (sys_settings.max_acceptance_rounds if sys_settings else 3) or 3
            _limit = max_acceptance_rounds if max_acceptance_rounds > 0 else 999999

            for round_num in range(_limit):
                # 更新验收次数
                task_obj = db.query(Task).filter(Task.id == task_id).first()
                if task_obj:
                    task_obj.acceptance_attempts = round_num + 1
                    task_obj.acceptance_status = "in_review"
                    db.commit()

                yield send_event("status", {"message": f"验收工程师正在检查（第{round_num+1}轮）..."})

                acceptance_result = await loop.run_in_executor(
                    ai_pool,
                    partial(run_acceptance_check,
                        api_key=cfg.api_key, model=model_to_use,
                        base_url=cfg.api_base_url or None,
                        criteria=acceptance_criteria,
                        task_result=reply,
                        workspace=workspace,
                        tool_calls_log=all_tool_calls
                    )
                )

                yield send_event("acceptance_result", {
                    "task_id": task_id,
                    "round": round_num + 1,
                    "passed": acceptance_result.get("passed", True),
                    "results": acceptance_result.get("results", []),
                    "max_rounds": max_acceptance_rounds if max_acceptance_rounds > 0 else 0
                })

                if acceptance_result.get("passed", True):
                    # 验收通过
                    logger.info(f"[Acceptance] 第 {round_num+1} 轮验收: 通过")
                    if task_obj:
                        task_obj.acceptance_status = "passed"
                        db.commit()
                    break

                # 验收未通过
                logger.info(f"[Acceptance] 第 {round_num+1} 轮验收: 未通过")
                for item in acceptance_result.get("results", []):
                    status = item.get('status', 'passed' if item.get('passed', True) else 'failed')
                    reason = str(item.get('reason', ''))[:100]
                    logger.info(f"[Acceptance]   - [{status}] {reason}")

                # 验收未通过，进行修复
                if round_num < _limit - 1:
                    yield send_event("status", {"message": f"验收未通过，正在修复（第{round_num+1}轮）..."})

                    # 格式化验收报告，作为上下文发送给执行AI
                    acceptance_report = _format_acceptance_report(round_num + 1, acceptance_result)

                    # 重建精简的修复上下文（避免消息链膨胀）
                    fix_messages = [
                        SystemMessage(content=system_prompt + "\n\n## 修复模式\n你现在处于修复模式。验收工程师发现了问题，请根据验收报告修复。"),
                        HumanMessage(content=f"原始任务: {user_msg}"),
                        HumanMessage(content=f"已执行的操作摘要:\n" + "\n".join([
                            f"- [{'成功' if tc['success'] else '失败'}] {tc['tool_name']}: {tc.get('description', '')[:100]}"
                            for tc in all_tool_calls
                        ])),
                        HumanMessage(content=acceptance_report),
                        HumanMessage(content="请根据验收报告中的失败项进行针对性修复，确保所有验收标准通过。"),
                    ]

                    for fix_i in range(max_iterations):
                        logger.info(f"[LLM Request] Fix round {round_num+1}-{fix_i+1}, messages ({len(fix_messages)} msgs)")
                        response = await loop.run_in_executor(ai_pool, llm_with_tools.invoke, fix_messages)

                        # 清理 response content
                        resp_content = response.content or ""
                        resp_content = _strip_context_summary(resp_content)
                        _fix_tc = ', '.join([tc.get('name','?') for tc in (response.tool_calls or [])]) or 'none'
                        logger.info(f"[LLM Response] Fix round {round_num+1}-{fix_i+1}, content: {resp_content}, tool_calls: {_fix_tc}")

                        if not response.tool_calls:
                            # 修复完成，收集结果
                            reply = resp_content
                            break

                        # 执行工具调用（复用现有逻辑）
                        fix_messages.append(response)
                        for tool_call in response.tool_calls:
                            tool_name = tool_call.get("name", "")
                            tool_args = tool_call.get("args", {})
                            tool_id = tool_call.get("id", "")

                            tool_fn = tool_map.get(tool_name)
                            if tool_fn:
                                try:
                                    result = await loop.run_in_executor(ai_pool, tool_fn.invoke, tool_args)
                                except Exception as e:
                                    result = f"工具执行错误: {e}"
                            else:
                                result = f"工具 {tool_name} 未找到"

                            logger.info(f"[Tool Result] {tool_name}: {str(result)}")
                            fix_messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))

                            result_str = str(result)
                            yield send_event("tool_end", {
                                "tool": tool_name,
                                "result": result_str[:500],
                                "success": _is_tool_success(result)
                            })
                else:
                    # 达到最大验收轮数
                    if task_obj:
                        task_obj.acceptance_status = "failed"
                        db.commit()
                    yield send_event("status", {"message": "已达最大验收轮数，任务标记为验收失败"})
        elif confirmed_task_id and not _has_acceptance_final:
            # 无验收标准，跳过验收流程，直接完成任务
            logger.info(f"[Acceptance] Task #{task_id} 无验收标准，跳过验收流程")
            yield send_event("status", {"message": "无验收标准，直接完成任务"})

        if task_record:
            try:
                task_record.status = "completed"
                task_record.progress = 100
                task_record.progress_message = "任务完成"
                task_record.ai_reply = reply
                db.commit()
            except Exception:
                pass

        # 标记剩余步骤为完成
        if plan_steps_db:
            for ws in plan_steps_db:
                if ws.status in ("pending", "running"):
                    ws.status = "completed"
            db.commit()

        logger.info(f"[Reply] 最终回复: {reply if reply else '(empty)'}")
        yield send_event("reply", {
            "reply": reply,
            "model_name": model_to_use,
            "vendor": cfg.vendor or "openai",
            "config_name": cfg.name,
            "tool_calls": all_tool_calls,
            "intent": intent,
            "task_id": task_id,
        })
        # 保存对话消息到数据库
        _save_chat_messages(
            db=db,
            current_user=current_user,
            agent_id=payload.agent_id,
            user_msg=user_msg,
            reply=reply,
            intent=intent,
            task_id=task_id,
            model_name=model_to_use,
            config_name=cfg.name,
            tool_calls=all_tool_calls if all_tool_calls else None,
        )
        if task_id is not None:
            _abort_signals.pop(task_id, None)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


class ConfirmCriteriaRequest(BaseModel):
    task_id: int
    criteria: list  # 用户可能编辑过的验收标准
    agent_id: Optional[int] = None

@router.post("/chat/confirm-criteria")
def confirm_criteria_and_execute(
    req: ConfirmCriteriaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """用户确认验收标准后，更新 Task 并返回确认状态"""
    logger.info(f"[Chat.confirm_criteria_and_execute] 入参: task_id={req.task_id}, criteria数={len(req.criteria)}, agent_id={req.agent_id}")
    from models.task import Task
    
    task = db.query(Task).filter(Task.id == req.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 更新验收标准（用户可能编辑过）
    task.acceptance_criteria = req.criteria
    task.acceptance_status = "confirmed"
    db.commit()
    
    logger.info(f"[Chat.confirm_criteria_and_execute] 返回: task_id={req.task_id} 已确认")
    return {"status": "confirmed", "task_id": req.task_id, "message": "验收标准已确认，请发送消息触发执行"}
