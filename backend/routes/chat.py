from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import ApiKeyConfig, get_db, User
from schemas.chat import ChatRequest, ChatResponse, ChatConfigItem
from dependencies.auth import get_current_user
from services.llm_service import get_llm_for_config
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

router = APIRouter()

@router.get("/configs", response_model=list[ChatConfigItem])
def list_chat_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """返回可用于对话的 Key 配置列表（仅展示 id/name/vendor/model）"""
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
    return result

@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """使用指定配置进行对话"""
    # 查找配置
    cfg = db.query(ApiKeyConfig).filter(ApiKeyConfig.id == payload.config_id).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="配置不存在")
    if not cfg.api_key:
        raise HTTPException(status_code=400, detail="该配置未填写 API Key")

    # 确定使用哪个模型（如果请求中指定了，则覆盖默认）
    model_to_use = payload.model or cfg.model_name

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

    try:
        response = llm_instance.invoke(lc_messages)
        reply = response.content if hasattr(response, 'content') else str(response)
        reply = reply.strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"模型调用失败: {str(e)}")

    return ChatResponse(
        reply=reply,
        model_name=model_to_use,
        vendor=cfg.vendor or "openai",
        config_name=cfg.name,
    )


def _build_lc_messages(messages: list) -> list:
    """将 API 消息转换为 LangChain 消息对象"""
    role_map = {
        "system": SystemMessage,
        "user": HumanMessage,
        "assistant": AIMessage,
    }
    result = []
    for m in messages:
        cls = role_map.get(m.role, HumanMessage)
        result.append(cls(content=m.content))
    return result
