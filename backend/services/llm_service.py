import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

# 全局 LLM 实例缓存（dict: config_id → LLM instance）
_llm_cache: dict = {}
# 默认使用的 LLM 实例
llm = None

def _build_llm(model_name: str, api_key: str, api_base_url: str = "") -> Optional[ChatOpenAI]:
    """构造 LLM 实例（Chat Completions API）"""
    logger.info(f"[LLMService._build_llm] 入参: model_name={model_name}, api_base_url={api_base_url}")
    if ChatOpenAI is None:
        logger.info("[LLMService._build_llm] 返回: None (ChatOpenAI不可用)")
        return None
    if not api_key:
        logger.info("[LLMService._build_llm] 返回: None (api_key为空)")
        return None
    kwargs = {"api_key": api_key, "model": model_name}
    kwargs["timeout"] = 300
    if api_base_url:
        kwargs["base_url"] = api_base_url
    result = ChatOpenAI(**kwargs)
    logger.info(f"[LLMService._build_llm] 返回: LLM实例(model={model_name})")
    return result

def reload_llm_from_configs(db=None):
    """从数据库 ApiKeyConfig 加载所有配置，更新 LLM 缓存和默认实例"""
    logger.info("[LLMService.reload_llm_from_configs] 入参: db=%s" % ('provided' if db else 'None'))
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
        logger.info(f"[LLMService.reload_llm_from_configs] 缓存更新完成: {len(_llm_cache)} 个配置, 默认LLM={'已设置' if llm else '未设置'}")

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
    logger.info("[LLMService.load_llm_from_db] 入参: 无")
    reload_llm_from_configs()
    logger.info("[LLMService.load_llm_from_db] 返回: 完成")

def get_llm_for_config(config_id: int) -> Optional[ChatOpenAI]:
    """按配置 ID 获取 LLM 实例"""
    logger.info(f"[LLMService.get_llm_for_config] 入参: config_id={config_id}")
    result = _llm_cache.get(config_id)
    logger.info(f"[LLMService.get_llm_for_config] 返回: {'found' if result else 'None'}")
    return result

def get_llm_response(prompt):
    """使用默认 LLM 获取响应"""
    logger.info(f"[LLMService.get_llm_response] 入参: prompt={str(prompt)[:100]}")
    if not llm:
        logger.info("[LLMService.get_llm_response] 返回: 未配置LLM")
        return "语言模型未配置，请前往设置页面配置 API Key"

    try:
        try:
            from langchain_core.messages import HumanMessage
            response = llm.invoke([HumanMessage(content=prompt)])
        except ImportError:
            response = llm.invoke([{"role": "user", "content": prompt}])
        content = response.content if hasattr(response, 'content') else str(response)
        logger.info(f"[LLMService.get_llm_response] 返回: {content[:100]}")
        return content.strip()
    except Exception as e:
        logger.error(f"[LLMService.get_llm_response] 异常: {e}", exc_info=True)
        return f"Error: {str(e)}"
