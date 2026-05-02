import os
import platform
import subprocess
import shutil
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from dependencies.auth import get_current_user
from models.database import get_db
from models.user import User
from models.environment import EnvironmentInfo
from schemas.environment import (
    EnvironmentDetectResponse,
    EnvironmentInfoResponse,
    EnvironmentUpdateRequest,
)

router = APIRouter()
logger = logging.getLogger(__name__)

NIX_DIR = ".nix"


def _get_nix_dir(workspace: str = None) -> str:
    """获取.nix目录路径"""
    base = workspace or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    nix_dir = os.path.join(base, NIX_DIR)
    os.makedirs(nix_dir, exist_ok=True)
    return nix_dir


def _save_env_to_file(env_data: dict, workspace: str = None):
    """保存环境信息到 .nix/environment.json"""
    nix_dir = _get_nix_dir(workspace)
    filepath = os.path.join(nix_dir, "environment.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(env_data, f, ensure_ascii=False, indent=2)
    logger.info(f"环境信息已保存到: {filepath}")


def _load_env_from_file(workspace: str = None) -> dict:
    """从 .nix/environment.json 加载环境信息"""
    nix_dir = _get_nix_dir(workspace)
    filepath = os.path.join(nix_dir, "environment.json")
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def _detect_environment() -> dict:
    """自动检测当前服务器环境信息"""
    info = {}

    # 操作系统信息
    system = platform.system()
    if system == "Darwin":
        info["os_name"] = "macOS"
        try:
            info["os_version"] = subprocess.check_output(
                ["sw_vers", "-productVersion"], text=True
            ).strip()
        except Exception:
            info["os_version"] = platform.mac_ver()[0]
        try:
            info["device_model"] = subprocess.check_output(
                ["sysctl", "-n", "hw.model"], text=True
            ).strip()
        except Exception:
            info["device_model"] = "Mac"
    elif system == "Linux":
        info["os_name"] = "Linux"
        info["os_version"] = platform.release()
        info["device_model"] = "Linux Server"
    elif system == "Windows":
        info["os_name"] = "Windows"
        info["os_version"] = platform.version()
        info["device_model"] = "Windows PC"

    info["architecture"] = platform.machine()  # arm64, x86_64
    info["hostname"] = platform.node()

    # Shell检测
    info["shell"] = os.environ.get("SHELL", "unknown")

    # 技术栈检测
    tech_stack = {}

    # Python
    tech_stack["python"] = platform.python_version()

    # Node.js
    node_path = shutil.which("node")
    if node_path:
        try:
            tech_stack["node"] = subprocess.check_output(
                ["node", "--version"], text=True
            ).strip()
        except Exception:
            pass

    # npm
    npm_path = shutil.which("npm")
    if npm_path:
        try:
            tech_stack["npm"] = subprocess.check_output(
                ["npm", "--version"], text=True
            ).strip()
        except Exception:
            pass

    # Git
    git_path = shutil.which("git")
    if git_path:
        try:
            git_output = subprocess.check_output(
                ["git", "--version"], text=True
            ).strip()
            tech_stack["git"] = git_output.replace("git version ", "")
        except Exception:
            pass

    # Docker
    docker_path = shutil.which("docker")
    if docker_path:
        try:
            docker_output = subprocess.check_output(
                ["docker", "--version"], text=True
            ).strip()
            tech_stack["docker"] = docker_output.split(",")[0].replace("Docker version ", "")
        except Exception:
            pass

    # pip
    pip_path = shutil.which("pip3") or shutil.which("pip")
    if pip_path:
        try:
            pip_output = subprocess.check_output(
                [pip_path, "--version"], text=True
            ).strip()
            tech_stack["pip"] = pip_output.split(" ")[1]
        except Exception:
            pass

    info["tech_stack"] = tech_stack

    # 包管理器检测
    package_managers = []
    for pm in ["brew", "npm", "yarn", "pnpm", "pip3", "pip", "cargo", "go"]:
        if shutil.which(pm):
            package_managers.append(pm)
    info["package_managers"] = package_managers

    # 终端注意事项
    terminal_notes = []
    if system == "Darwin":
        terminal_notes.extend([
            "macOS: 使用 open 代替 xdg-open",
            "macOS: 使用 pbcopy/pbpaste 代替 xclip",
            "macOS: sed 命令需要 -i '' 而非 -i",
            "macOS: 不支持 apt-get/yum，使用 brew 安装系统工具",
            "macOS: 使用 diskutil 代替 fdisk",
        ])
    elif system == "Linux":
        terminal_notes.append("Linux: 根据发行版使用 apt-get 或 yum")
    elif system == "Windows":
        terminal_notes.extend([
            "Windows: 使用 PowerShell 或 cmd",
            "Windows: 路径分隔符使用 \\",
        ])
    info["terminal_notes"] = terminal_notes

    return info


@router.get("/detect", response_model=EnvironmentDetectResponse)
def detect_environment(current_user: User = Depends(get_current_user)):
    """自动检测当前环境信息"""
    info = _detect_environment()
    return EnvironmentDetectResponse(**info)


@router.post("/save", response_model=EnvironmentInfoResponse)
def save_environment(
    workspace: str = Query(None, description="工作目录路径"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """检测并保存环境信息到数据库和文件"""
    info = _detect_environment()

    # 保存到文件
    _save_env_to_file(info, workspace)

    # 查找现有记录
    existing = (
        db.query(EnvironmentInfo)
        .filter(EnvironmentInfo.user_id == current_user.id)
        .first()
    )

    if existing:
        # 更新现有记录
        for key, value in info.items():
            setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # 创建新记录
        env = EnvironmentInfo(user_id=current_user.id, **info)
        db.add(env)
        db.commit()
        db.refresh(env)
        return env


@router.get("/auto", response_model=EnvironmentDetectResponse)
def auto_detect_environment(
    workspace: str = Query(None, description="工作目录路径"),
    current_user: User = Depends(get_current_user),
):
    """自动检测环境：如果.nix/environment.json存在则直接返回，否则检测并保存"""
    # 尝试从文件加载
    cached = _load_env_from_file(workspace)
    if cached:
        return EnvironmentDetectResponse(**cached)

    # 首次检测
    info = _detect_environment()
    _save_env_to_file(info, workspace)

    # 同时保存到数据库
    db = next(get_db())
    try:
        existing = (
            db.query(EnvironmentInfo)
            .filter(EnvironmentInfo.user_id == current_user.id)
            .first()
        )
        if existing:
            for key, value in info.items():
                setattr(existing, key, value)
            db.commit()
            db.refresh(existing)
        else:
            env = EnvironmentInfo(user_id=current_user.id, **info)
            db.add(env)
            db.commit()
            db.refresh(env)
    finally:
        db.close()

    return EnvironmentDetectResponse(**info)


@router.get("/summary")
def get_environment_summary(
    workspace: str = Query(None, description="工作目录路径"),
    current_user: User = Depends(get_current_user),
):
    """返回精简的环境摘要文本，适合注入AI对话上下文"""
    cached = _load_env_from_file(workspace)
    if not cached:
        cached = _detect_environment()
        _save_env_to_file(cached, workspace)

    # 构建精简摘要
    summary_lines = []
    summary_lines.append(f"操作系统: {cached.get('os_name', 'unknown')} {cached.get('os_version', '')}")
    summary_lines.append(f"架构: {cached.get('architecture', 'unknown')}")
    summary_lines.append(f"Shell: {cached.get('shell', 'unknown')}")

    if cached.get('tech_stack'):
        tech = ', '.join([f"{k}={v}" for k, v in cached['tech_stack'].items()])
        summary_lines.append(f"技术栈: {tech}")

    if cached.get('package_managers'):
        summary_lines.append(f"包管理器: {', '.join(cached['package_managers'])}")

    if cached.get('terminal_notes'):
        summary_lines.append("终端注意事项:")
        for note in cached['terminal_notes']:
            summary_lines.append(f"  - {note}")

    return {"summary": "\n".join(summary_lines), "raw": cached}


@router.get("/info", response_model=EnvironmentInfoResponse)
def get_environment_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取已保存的环境信息"""
    env = (
        db.query(EnvironmentInfo)
        .filter(EnvironmentInfo.user_id == current_user.id)
        .first()
    )
    if not env:
        raise HTTPException(
            status_code=404, detail="未检测到环境信息，请先执行环境检测"
        )
    return env


@router.put("/update", response_model=EnvironmentInfoResponse)
def update_environment(
    request: EnvironmentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动更新环境信息"""
    env = (
        db.query(EnvironmentInfo)
        .filter(EnvironmentInfo.user_id == current_user.id)
        .first()
    )
    if not env:
        raise HTTPException(
            status_code=404, detail="未检测到环境信息，请先执行环境检测"
        )

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(env, key, value)
    db.commit()
    db.refresh(env)
    return env
