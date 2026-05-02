from pydantic import BaseModel
from typing import Optional, List


class SkillTreeNode(BaseModel):
    name: str
    path: str  # 相对于skills根目录的路径
    type: str  # "file" 或 "directory"
    children: Optional[List['SkillTreeNode']] = None


class SkillTreeResponse(BaseModel):
    tree: List[SkillTreeNode]


class SkillFileResponse(BaseModel):
    path: str
    name: str
    content: str
    size: int


class SkillFileCreateRequest(BaseModel):
    path: str  # 相对路径，如 "coding/python-style.md"
    content: str = ""


class SkillFileUpdateRequest(BaseModel):
    path: str
    content: str


class SkillDirectoryCreateRequest(BaseModel):
    path: str  # 如 "coding" 或 "database/mysql"


class SkillOperationResponse(BaseModel):
    success: bool
    message: str
    path: Optional[str] = None
