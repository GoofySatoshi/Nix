"""
Workspace API - 工作目录管理

前端通过这个 API 管理工作目录，不再用 localStorage。
"""

import os
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from dependencies.auth import get_current_user
from models import User

logger = logging.getLogger(__name__)
router = APIRouter()


class WorkspaceInfo(BaseModel):
    path: str
    exists: bool
    is_writable: bool


class SetWorkspaceRequest(BaseModel):
    path: str


# 全局工作目录状态
_current_workspace: str = os.path.expanduser("~")


@router.get("", response_model=WorkspaceInfo)
def get_workspace(current_user: User = Depends(get_current_user)):
    """获取当前工作目录"""
    global _current_workspace
    exists = os.path.isdir(_current_workspace)
    is_writable = os.access(_current_workspace, os.W_OK) if exists else False
    return WorkspaceInfo(
        path=_current_workspace,
        exists=exists,
        is_writable=is_writable,
    )


@router.put("")
def set_workspace(
    req: SetWorkspaceRequest,
    current_user: User = Depends(get_current_user),
):
    """设置工作目录"""
    global _current_workspace
    path = os.path.expanduser(req.path)
    path = os.path.abspath(path)

    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"目录不存在: {path}")
    if not os.access(path, os.W_OK):
        raise HTTPException(status_code=400, detail=f"目录不可写: {path}")

    _current_workspace = path

    # 同步更新 ToolRegistry
    try:
        from core.tool_registry import get_tool_registry
        get_tool_registry().set_workspace(path)
    except Exception as e:
        logger.warning(f"更新 ToolRegistry 工作目录失败: {e}")

    logger.info(f"工作目录已更新: {path}")
    return {"path": path, "message": "工作目录已更新"}


@router.get("/list")
def list_subdirectories(
    path: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """列出子目录（供前端目录浏览器使用）"""
    global _current_workspace
    target = path or _current_workspace
    target = os.path.expanduser(target)
    target = os.path.abspath(target)

    if not os.path.isdir(target):
        raise HTTPException(status_code=400, detail=f"目录不存在: {target}")

    directories = []
    try:
        for item in sorted(os.listdir(target)):
            if item.startswith('.'):
                continue
            item_path = os.path.join(target, item)
            if os.path.isdir(item_path):
                directories.append({
                    "name": item,
                    "path": item_path,
                    "readable": os.access(item_path, os.R_OK),
                })
    except PermissionError:
        raise HTTPException(status_code=403, detail="无权限访问该目录")

    parent = os.path.dirname(target)
    return {
        "current_path": target,
        "parent_path": parent if parent != target else "",
        "directories": directories,
    }
