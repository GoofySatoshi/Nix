import os
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from dependencies.auth import get_current_user
from models.user import User
from models.database import get_db
from models.skill import Skill
from schemas.skill import (
    SkillTreeNode,
    SkillTreeResponse,
    SkillFileResponse,
    SkillFileCreateRequest,
    SkillFileUpdateRequest,
    SkillDirectoryCreateRequest,
    SkillOperationResponse,
)
from services.skill_service import write_skill_file, delete_skill_file as svc_delete_skill_file
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

# Skills 根目录（项目根目录下的 skills/）
SKILLS_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "skills"
)


def _ensure_skills_root():
    """确保skills根目录存在"""
    os.makedirs(SKILLS_ROOT, exist_ok=True)


def _validate_skill_path(path: str) -> str:
    """验证路径在skills目录内，返回绝对路径"""
    _ensure_skills_root()
    abs_path = os.path.realpath(os.path.join(SKILLS_ROOT, path))
    if not abs_path.startswith(os.path.realpath(SKILLS_ROOT)):
        raise HTTPException(status_code=403, detail="路径不在Skills目录内")
    return abs_path


def _build_tree(dir_path: str, rel_base: str = "") -> list:
    """递归构建目录树"""
    items = []
    try:
        entries = sorted(os.listdir(dir_path))
    except OSError:
        return items

    # 先目录后文件
    dirs = []
    files = []
    for entry in entries:
        if entry.startswith('.'):
            continue
        full_path = os.path.join(dir_path, entry)
        rel_path = os.path.join(rel_base, entry) if rel_base else entry
        if os.path.isdir(full_path):
            dirs.append((entry, full_path, rel_path))
        elif entry.endswith('.md'):
            files.append((entry, full_path, rel_path))

    for name, full, rel in dirs:
        items.append(
            SkillTreeNode(
                name=name, path=rel, type="directory", children=_build_tree(full, rel)
            )
        )
    for name, full, rel in files:
        items.append(SkillTreeNode(name=name, path=rel, type="file"))

    return items


@router.get("/tree", response_model=SkillTreeResponse)
async def get_skill_tree(current_user: User = Depends(get_current_user)):
    """获取Skills目录树"""
    _ensure_skills_root()
    tree = _build_tree(SKILLS_ROOT)
    return SkillTreeResponse(tree=tree)


@router.get("/file", response_model=SkillFileResponse)
async def get_skill_file(
    path: str = Query(..., description="文件相对路径"),
    current_user: User = Depends(get_current_user),
):
    """读取Skill文件内容"""
    abs_path = _validate_skill_path(path)
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    if not abs_path.endswith('.md'):
        raise HTTPException(status_code=400, detail="仅支持Markdown文件")
    content = open(abs_path, 'r', encoding='utf-8').read()
    return SkillFileResponse(
        path=path,
        name=os.path.basename(path),
        content=content,
        size=len(content),
    )


@router.post("/file", response_model=SkillOperationResponse)
async def create_skill_file(
    request: SkillFileCreateRequest,
    current_user: User = Depends(get_current_user),
):
    """创建Skill文件"""
    if not request.path.endswith('.md'):
        request.path += '.md'
    abs_path = _validate_skill_path(request.path)
    if os.path.exists(abs_path):
        raise HTTPException(status_code=409, detail="文件已存在")
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, 'w', encoding='utf-8') as f:
        f.write(request.content)
    logger.info(f"Skill文件已创建: {request.path}")
    return SkillOperationResponse(success=True, message="文件创建成功", path=request.path)


@router.put("/file", response_model=SkillOperationResponse)
async def update_skill_file(
    request: SkillFileUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    """更新Skill文件"""
    abs_path = _validate_skill_path(request.path)
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    with open(abs_path, 'w', encoding='utf-8') as f:
        f.write(request.content)
    logger.info(f"Skill文件已更新: {request.path}")
    return SkillOperationResponse(success=True, message="文件更新成功", path=request.path)


@router.delete("/file", response_model=SkillOperationResponse)
async def delete_skill_file(
    path: str = Query(...),
    current_user: User = Depends(get_current_user),
):
    """删除Skill文件"""
    abs_path = _validate_skill_path(path)
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    os.remove(abs_path)
    logger.info(f"Skill文件已删除: {path}")
    return SkillOperationResponse(success=True, message="文件删除成功", path=path)


@router.post("/directory", response_model=SkillOperationResponse)
async def create_skill_directory(
    request: SkillDirectoryCreateRequest,
    current_user: User = Depends(get_current_user),
):
    """创建Skills目录"""
    abs_path = _validate_skill_path(request.path)
    if os.path.exists(abs_path):
        raise HTTPException(status_code=409, detail="目录已存在")
    os.makedirs(abs_path, exist_ok=True)
    logger.info(f"Skill目录已创建: {request.path}")
    return SkillOperationResponse(success=True, message="目录创建成功", path=request.path)


@router.delete("/directory", response_model=SkillOperationResponse)
async def delete_skill_directory(
    path: str = Query(...),
    current_user: User = Depends(get_current_user),
):
    """删除Skills目录（仅空目录）"""
    abs_path = _validate_skill_path(path)
    if not os.path.isdir(abs_path):
        raise HTTPException(status_code=404, detail="目录不存在")
    if os.listdir(abs_path):
        raise HTTPException(status_code=400, detail="目录不为空，请先删除内部文件")
    os.rmdir(abs_path)
    logger.info(f"Skill目录已删除: {path}")
    return SkillOperationResponse(success=True, message="目录删除成功", path=path)


# === Skill CRUD Schemas ===

class SkillCreate(BaseModel):
    name: str
    description: Optional[str] = None
    content: str
    scope: str  # "agent" 或 "project"
    keywords: Optional[list[str]] = None
    category: Optional[str] = "general"
    agent_id: Optional[int] = None
    workspace: Optional[str] = None


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    keywords: Optional[list[str]] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None


class SkillResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    content: str
    scope: str
    keywords: Optional[list[str]]
    category: Optional[str]
    agent_id: Optional[int]
    is_active: bool

    class Config:
        from_attributes = True


# === Skill CRUD Routes ===

@router.post("/manage", response_model=SkillResponse)
async def create_skill(
    payload: SkillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建 Skill"""
    if payload.scope not in ("agent", "project"):
        raise HTTPException(status_code=400, detail="scope 必须是 'agent' 或 'project'")

    if payload.scope == "agent" and payload.agent_id is None:
        raise HTTPException(status_code=400, detail="scope=agent 时必须提供 agent_id")

    # 确定 workspace（项目级 skill 需要）
    workspace = payload.workspace
    if not workspace:
        workspace = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    skill = Skill(
        name=payload.name,
        description=payload.description,
        content=payload.content,
        scope=payload.scope,
        keywords=payload.keywords or [],
        category=payload.category,
        agent_id=payload.agent_id,
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)

    if payload.scope == "project":
        try:
            write_skill_file(
                workspace=workspace,
                name=skill.name,
                description=skill.description or "",
                keywords=skill.keywords or [],
                category=skill.category or "general",
                content=skill.content,
            )
        except Exception as e:
            logger.warning(f"写入项目级 skill 文件失败: {e}")

    return skill


@router.get("/manage", response_model=list[SkillResponse])
async def list_skills(
    scope: Optional[str] = Query(None),
    agent_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Skill 列表，支持筛选"""
    query = db.query(Skill)
    if scope is not None:
        query = query.filter(Skill.scope == scope)
    if agent_id is not None:
        query = query.filter(Skill.agent_id == agent_id)
    if is_active is not None:
        query = query.filter(Skill.is_active == is_active)
    skills = query.order_by(Skill.id.desc()).all()
    return skills


@router.get("/manage/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Skill 详情"""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    return skill


@router.put("/manage/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: int,
    payload: SkillUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新 Skill"""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")

    update_fields = {
        "name": payload.name,
        "description": payload.description,
        "content": payload.content,
        "keywords": payload.keywords,
        "category": payload.category,
        "is_active": payload.is_active,
    }
    for field, value in update_fields.items():
        if value is not None:
            setattr(skill, field, value)

    db.commit()
    db.refresh(skill)

    if skill.scope == "project":
        workspace = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        try:
            write_skill_file(
                workspace=workspace,
                name=skill.name,
                description=skill.description or "",
                keywords=skill.keywords or [],
                category=skill.category or "general",
                content=skill.content,
            )
        except Exception as e:
            logger.warning(f"更新项目级 skill 文件失败: {e}")

    return skill


@router.delete("/manage/{skill_id}")
async def delete_skill(
    skill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除 Skill"""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")

    if skill.scope == "project":
        workspace = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        try:
            svc_delete_skill_file(workspace=workspace, name=skill.name)
        except Exception as e:
            logger.warning(f"删除项目级 skill 文件失败: {e}")

    db.delete(skill)
    db.commit()
    return {"success": True, "message": "Skill 已删除"}


@router.get("/search", response_model=list[SkillResponse])
async def search_skills(
    q: str = Query(..., description="搜索关键词"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """关键词搜索 Skill（在 name、description、keywords 中搜索）"""
    from sqlalchemy import or_

    search_pattern = f"%{q}%"
    skills = db.query(Skill).filter(
        or_(
            Skill.name.ilike(search_pattern),
            Skill.description.ilike(search_pattern),
            Skill.keywords.contains(q),
        )
    ).order_by(Skill.id.desc()).all()
    return skills

