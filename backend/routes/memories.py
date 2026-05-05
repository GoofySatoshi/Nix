import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import get_db, User
from dependencies.auth import get_current_user
from services.memory_service import (
    read_soul_memory, write_soul_memory, add_memory,
    delete_memory, update_memory, MEMORY_CATEGORIES,
    get_soul_file_path, read_project_memory,
    get_full_memory_for_agent, PROJECT_CATEGORIES
)
from schemas.memory import (
    MemoryListResponse, MemoryAddRequest, MemoryDeleteRequest,
    MemoryUpdateRequest, MemoryRefineRequest, MemoryRefineResponse,
    MemoryOperationResponse
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/categories")
def get_categories(current_user: User = Depends(get_current_user)):
    """获取记忆分类列表"""
    return {
        "categories": MEMORY_CATEGORIES,
        "project_categories": PROJECT_CATEGORIES,
    }


@router.get("/project")
def get_project_memories(
    workspace: str = None,
    current_user: User = Depends(get_current_user)
):
    """获取项目级记忆"""
    data = read_project_memory(workspace)
    return data


@router.get("/{agent_name}", response_model=MemoryListResponse)
def get_agent_memories(
    agent_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取指定智能体的灵魂记忆"""
    data = read_soul_memory(agent_name)
    return MemoryListResponse(**data)


@router.get("/{agent_name}/full")
def get_full_memories(
    agent_name: str,
    workspace: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取智能体的完整记忆（项目级 + 智能体级合并）"""
    memories = get_full_memory_for_agent(agent_name, workspace)
    return {"agent_name": agent_name, "memories": memories}


@router.post("/{agent_name}/add", response_model=MemoryOperationResponse)
def add_agent_memory(
    agent_name: str,
    req: MemoryAddRequest,
    current_user: User = Depends(get_current_user)
):
    """添加一条记忆"""
    result = add_memory(agent_name, req.category, req.content, req.workspace)
    return MemoryOperationResponse(**result)


@router.post("/{agent_name}/delete", response_model=MemoryOperationResponse)
def delete_agent_memory(
    agent_name: str,
    req: MemoryDeleteRequest,
    current_user: User = Depends(get_current_user)
):
    """删除一条记忆"""
    result = delete_memory(agent_name, req.category, req.content, req.workspace)
    return MemoryOperationResponse(**result)


@router.put("/{agent_name}/update", response_model=MemoryOperationResponse)
def update_agent_memory(
    agent_name: str,
    req: MemoryUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    """更新一条记忆"""
    result = update_memory(agent_name, req.category, req.old_content, req.new_content, req.workspace)
    return MemoryOperationResponse(**result)


@router.post("/{agent_name}/refine", response_model=MemoryRefineResponse)
def refine_agent_memories(
    agent_name: str,
    req: MemoryRefineRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """整理/提炼智能体的灵魂记忆（使用 LLM）"""
    from models import ApiKeyConfig
    from services.llm_service import _build_llm

    # 获取当前记忆
    data = read_soul_memory(agent_name)
    memories = data["memories"]

    if not memories:
        return MemoryRefineResponse(
            success=False, message="没有需要整理的记忆",
            refined_memories=[], raw_content=""
        )

    # 查找可用的 LLM 配置
    cfg = None
    if req.config_id:
        cfg = db.query(ApiKeyConfig).filter(ApiKeyConfig.id == req.config_id).first()
    else:
        cfg = db.query(ApiKeyConfig).filter(ApiKeyConfig.is_default == True).first()
        if not cfg:
            cfg = db.query(ApiKeyConfig).first()

    if not cfg or not cfg.api_key:
        raise HTTPException(status_code=400, detail="未找到可用的 API Key 配置，请先在系统设置中配置")

    model_to_use = req.model or cfg.model_name
    llm = _build_llm(model_to_use, cfg.api_key, cfg.api_base_url or "")
    if not llm:
        raise HTTPException(status_code=500, detail="无法初始化语言模型")

    # 构建提炼提示
    memory_text = "\n".join([
        f"[{m['category']}] {m['content']}" for m in memories
    ])

    refine_prompt = f"""你是一个记忆整理专家。请对以下智能体"{agent_name}"的记忆进行整理和提炼。

要求：
1. 合并重复或相似的记忆条目
2. 提炼关键信息，去除冗余描述
3. 按以下分类重新组织：用户偏好、项目规则、项目规范、工作经验、工具使用经验、错误教训
4. 每条记忆保持简洁精确（一两句话）
5. 保留所有有价值的信息，不要遗漏重要内容

当前记忆内容：
{memory_text}

请用以下 JSON 格式返回整理后的记忆（直接返回 JSON 数组，不要 markdown 代码块包裹）：
[{{"category": "分类名", "content": "记忆内容"}}, ...]"""

    try:
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            response = llm.invoke([
                SystemMessage(content="你是一个智能记忆整理助手，请严格按照要求输出 JSON 格式。"),
                HumanMessage(content=refine_prompt)
            ])
            result_text = response.content
        except ImportError:
            response = llm.invoke(refine_prompt)
            result_text = response.content if hasattr(response, 'content') else str(response)

        # 解析 JSON 结果
        import re
        # 尝试从返回中提取 JSON 数组
        json_match = re.search(r'\[[\s\S]*\]', result_text)
        if json_match:
            import json
            refined = json.loads(json_match.group())
        else:
            # 解析失败，返回原记忆
            return MemoryRefineResponse(
                success=False,
                message="LLM 返回格式解析失败，请重试",
                refined_memories=memories,
                raw_content=data.get("raw_content", "")
            )

        # 写入整理后的记忆
        write_soul_memory(agent_name, refined)
        new_data = read_soul_memory(agent_name)

        return MemoryRefineResponse(
            success=True,
            message=f"记忆整理完成，从 {len(memories)} 条优化为 {len(refined)} 条",
            refined_memories=new_data["memories"],
            raw_content=new_data["raw_content"]
        )
    except Exception as e:
        logger.error(f"记忆整理失败: {e}")
        raise HTTPException(status_code=500, detail=f"记忆整理失败: {str(e)}")
