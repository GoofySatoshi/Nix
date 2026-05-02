import os
from langchain_openai import ChatOpenAI
from typing import Optional

# 全局 LLM 实例缓存（dict: config_id → LLM instance）
_llm_cache: dict = {}
# 默认使用的 LLM 实例
llm = None

def _build_llm(model_name: str, api_key: str, api_base_url: str = "") -> Optional[ChatOpenAI]:
    """构造 LLM 实例（Chat Completions API）"""
    if not api_key:
        return None
    kwargs = {"api_key": api_key, "model": model_name}
    if api_base_url:
        kwargs["base_url"] = api_base_url
    return ChatOpenAI(**kwargs)

def reload_llm_from_configs(db=None):
    """从数据库 ApiKeyConfig 加载所有配置，更新 LLM 缓存和默认实例"""
    global llm, _llm_cache
    if db is None:
        from models.database import SessionLocal
        db = SessionLocal()
        close_db = True
    else:
        close_db = False

    try:
        from models import ApiKeyConfig
        configs = db.query(ApiKeyConfig).all()

        _llm_cache.clear()
        default_llm = None

        for cfg in configs:
            if cfg.api_key:
                try:
                    instance = _build_llm(cfg.model_name, cfg.api_key, cfg.api_base_url or "")
                    if instance:
                        _llm_cache[cfg.id] = instance
                        if cfg.is_default or default_llm is None:
                            default_llm = instance
                except Exception:
                    pass  # 单个配置加载失败不影响其他

        llm = default_llm

        # 如果数据库没有配置，回退到环境变量
        if llm is None:
            env_key = os.getenv("OPENAI_API_KEY", "")
            if env_key:
                try:
                    llm = _build_llm("gpt-3.5-turbo", env_key, "")
                except Exception:
                    pass
    finally:
        if close_db:
            db.close()

def load_llm_from_db():
    """应用启动时加载 LLM 配置"""
    reload_llm_from_configs()

def get_llm_for_config(config_id: int) -> Optional[ChatOpenAI]:
    """按配置 ID 获取 LLM 实例"""
    return _llm_cache.get(config_id)

def get_llm_response(prompt):
    """使用默认 LLM 获取响应"""
    if not llm:
        return "语言模型未配置，请前往设置页面配置 API Key"

    try:
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content if hasattr(response, 'content') else str(response)
        return content.strip()
    except Exception as e:
        return f"Error: {str(e)}"
