from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from models import ApiKeyConfig, get_db, User
from schemas.settings import (
    ApiKeyConfigCreate, ApiKeyConfigUpdate,
    ApiKeyConfigResponse, ApiKeyConfigListResponse,
    FetchModelsRequest, FetchModelsResponse
)
from dependencies.auth import get_current_user
from services.llm_service import reload_llm_from_configs
import httpx

router = APIRouter()

@router.get("", response_model=list[ApiKeyConfigListResponse])
def list_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rows = db.query(ApiKeyConfig).order_by(ApiKeyConfig.is_default.desc(), ApiKeyConfig.id).all()
    result = []
    for r in rows:
        result.append({
            "id": r.id, "name": r.name, "vendor": r.vendor or "openai",
            "model_name": r.model_name,
            "model_list": r.model_list or [r.model_name],
            "api_key": r.api_key,
            "api_base_url": r.api_base_url or "",
            "model_list_url": r.model_list_url or "",
            "is_default": r.is_default,
            "created_at": r.created_at, "updated_at": r.updated_at,
        })
    return result

@router.post("", response_model=ApiKeyConfigResponse)
def create_config(
    payload: ApiKeyConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 如果设为默认，先取消其他默认
    if payload.is_default:
        db.query(ApiKeyConfig).filter(ApiKeyConfig.is_default == True).update({"is_default": False})
    data = payload.model_dump()
    # 如果没有提供 model_list 或为空列表，默认使用 [model_name]
    ml = data.get("model_list")
    if not ml:
        data["model_list"] = [data.get("model_name", "gpt-3.5-turbo")]
    cfg = ApiKeyConfig(**data)
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    reload_llm_from_configs(db)
    return cfg

@router.get("/{config_id}", response_model=ApiKeyConfigResponse)
def get_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cfg = db.query(ApiKeyConfig).filter(ApiKeyConfig.id == config_id).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    return cfg

@router.put("/{config_id}", response_model=ApiKeyConfigResponse)
def update_config(
    config_id: int,
    payload: ApiKeyConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cfg = db.query(ApiKeyConfig).filter(ApiKeyConfig.id == config_id).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    if payload.is_default is True:
        db.query(ApiKeyConfig).filter(ApiKeyConfig.is_default == True).update({"is_default": False})
    update_data = payload.model_dump(exclude_unset=True)
    # 如果更新了 model_name 但没有更新 model_list，同步更新 model_list 的第一个元素
    if "model_name" in update_data and "model_list" not in update_data:
        if cfg.model_list and len(cfg.model_list) > 0:
            new_list = list(cfg.model_list)
            new_list[0] = update_data["model_name"]
            update_data["model_list"] = new_list
    # 如果提供了 model_list 但没有提供 model_name，同步 model_name 为列表第一个
    if "model_list" in update_data and "model_name" not in update_data:
        ml = update_data["model_list"]
        if ml and len(ml) > 0:
            update_data["model_name"] = ml[0]
    for k, v in update_data.items():
        setattr(cfg, k, v)
    db.commit()
    db.refresh(cfg)
    reload_llm_from_configs(db)
    return cfg

@router.delete("/{config_id}")
def delete_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cfg = db.query(ApiKeyConfig).filter(ApiKeyConfig.id == config_id).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    db.delete(cfg)
    db.commit()
    reload_llm_from_configs(db)
    return {"message": "Deleted"}

# -------- 获取模型列表 --------

@router.post("/fetch-models", response_model=FetchModelsResponse)
async def fetch_models(
    payload: FetchModelsRequest,
    current_user: User = Depends(get_current_user)
):
    """调用用户指定的 model_list_url，获取可用模型列表"""
    url = payload.model_list_url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="模型列表地址不能为空")
    if not payload.api_key.strip():
        raise HTTPException(status_code=400, detail="API Key 不能为空")

    headers = {"Authorization": f"Bearer {payload.api_key}"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="请求模型列表超时，请检查地址是否正确")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"模型列表接口返回错误: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"无法连接模型列表接口: {str(e)}")

    # 解析模型 ID 列表，兼容 OpenAI / OpenAI-compatible 格式 {"data":[{"id":"..."}]}
    models: list[str] = []
    if isinstance(data, dict) and "data" in data:
        for item in data["data"]:
            if isinstance(item, dict) and "id" in item:
                models.append(item["id"])
    elif isinstance(data, list):
        # 直接返回 list of strings
        for item in data:
            if isinstance(item, str):
                models.append(item)
            elif isinstance(item, dict) and "id" in item:
                models.append(item["id"])

    if not models:
        raise HTTPException(status_code=502, detail="无法解析模型列表，接口返回格式不兼容")

    # 按名称排序
    models.sort()
    return FetchModelsResponse(models=models, raw_count=len(models), vendor=payload.vendor)
