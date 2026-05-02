import os
import logging
import fnmatch
import re
import mimetypes
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from models import get_db, User
from dependencies.auth import get_current_user
from schemas.toolbox import (
    FileSearchRequest,
    FileSearchMatch,
    FileSearchResponse,
    FileLocateRequest,
    FileFindResponse,
    FileReadResponse,
    FileCreateRequest,
    FileUpdateRequest,
    FileOperationResponse,
    McpToolListResponse,
    McpToolInfo,
    McpToolParameter,
    McpExecuteRequest,
    McpExecuteResponse,
    AgentTaskSuggestRequest,
    AgentTaskModifyRequest,
    AgentTaskResponse,
    AgentTaskStatusResponse,
    TerminalExecuteRequest,
    FileKeywordMatch,
    FileKeywordSearchResponse,
    BrowserNavigateRequest,
    BrowserClickRequest,
    BrowserTypeRequest,
    BrowserExtractRequest,
    BrowserScreenshotRequest,
    BrowserActionResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)

WORKSPACE_ROOT = os.environ.get(
    "WORKSPACE_ROOT",
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


def validate_path(path: str) -> str:
    """验证路径在工作目录内，返回绝对路径"""
    abs_path = os.path.realpath(os.path.join(WORKSPACE_ROOT, path))
    real_workspace = os.path.realpath(WORKSPACE_ROOT)
    if abs_path != real_workspace and not abs_path.startswith(real_workspace + os.sep):
        raise HTTPException(status_code=403, detail="路径不在允许的工作目录内")
    return abs_path


def is_text_file(file_path: str) -> bool:
    """检查文件是否为文本文件"""
    mime, _ = mimetypes.guess_type(file_path)
    if mime:
        return mime.startswith("text/") or mime in (
            "application/json",
            "application/javascript",
            "application/xml",
            "application/x-yaml",
            "application/x-python-code",
        )
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            return b"\x00" not in chunk
    except Exception:
        return False


def get_file_lines(file_path: str) -> list[str]:
    """读取文件所有行"""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.readlines()


@router.post("/files/search", response_model=FileSearchResponse)
def file_search(
    req: FileSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    directory = validate_path(req.directory)

    if not os.path.exists(directory):
        raise HTTPException(status_code=404, detail="目录不存在")
    if not os.path.isdir(directory):
        raise HTTPException(status_code=400, detail="路径不是目录")

    matches = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

        for filename in files:
            if not fnmatch.fnmatch(filename, req.file_pattern):
                continue
            file_path = os.path.join(root, filename)
            if not is_text_file(file_path):
                continue

            try:
                lines = get_file_lines(file_path)
                for i, line in enumerate(lines):
                    if req.query in line:
                        context_before = [
                            l.rstrip("\n") for l in lines[max(0, i - 2) : i]
                        ]
                        context_after = [
                            l.rstrip("\n")
                            for l in lines[i + 1 : min(len(lines), i + 3)]
                        ]
                        rel_path = os.path.relpath(file_path, WORKSPACE_ROOT)
                        matches.append(
                            FileSearchMatch(
                                file_path=rel_path,
                                line_number=i + 1,
                                line_content=line.rstrip("\n"),
                                context_before=context_before,
                                context_after=context_after,
                            )
                        )
            except Exception as e:
                logger.warning(f"搜索文件失败 {file_path}: {e}")
                continue

    logger.info(
        f"用户 {current_user.username} 搜索 '{req.query}'，找到 {len(matches)} 个匹配"
    )
    return FileSearchResponse(matches=matches, total_count=len(matches))


@router.post("/files/locate")
def file_locate(
    req: FileLocateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    directory = validate_path(req.directory)

    if not os.path.exists(directory):
        raise HTTPException(status_code=404, detail="目录不存在")
    if not os.path.isdir(directory):
        raise HTTPException(status_code=400, detail="路径不是目录")

    results = []
    context = req.context_lines

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

        for filename in files:
            file_path = os.path.join(root, filename)
            if not is_text_file(file_path):
                continue

            try:
                lines = get_file_lines(file_path)
                for i, line in enumerate(lines):
                    if req.keyword in line:
                        rel_path = os.path.relpath(file_path, WORKSPACE_ROOT)
                        start = max(0, i - context)
                        end = min(len(lines), i + context + 1)
                        context_lines = [l.rstrip("\n") for l in lines[start:end]]
                        highlighted = [
                            f">> {l} <<" if idx == i - start else l
                            for idx, l in enumerate(context_lines)
                        ]
                        results.append(
                            {
                                "file_path": rel_path,
                                "line_number": i + 1,
                                "line_content": line.rstrip("\n"),
                                "context": highlighted,
                            }
                        )
            except Exception as e:
                logger.warning(f"定位文件失败 {file_path}: {e}")
                continue

    logger.info(
        f"用户 {current_user.username} 定位 '{req.keyword}'，找到 {len(results)} 个匹配"
    )
    return {"matches": results, "total_count": len(results)}


@router.get("/files/find", response_model=FileFindResponse)
def file_find(
    pattern: str = Query(..., description="匹配模式"),
    directory: Optional[str] = Query(".", description="搜索目录"),
    use_regex: bool = Query(False, description="是否使用正则匹配"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    directory = validate_path(directory)

    if not os.path.exists(directory):
        raise HTTPException(status_code=404, detail="目录不存在")
    if not os.path.isdir(directory):
        raise HTTPException(status_code=400, detail="路径不是目录")

    matched_files = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

        for filename in files:
            if use_regex:
                if re.search(pattern, filename):
                    matched_files.append(
                        os.path.relpath(os.path.join(root, filename), WORKSPACE_ROOT)
                    )
            else:
                if fnmatch.fnmatch(filename, pattern):
                    matched_files.append(
                        os.path.relpath(os.path.join(root, filename), WORKSPACE_ROOT)
                    )

    logger.info(
        f"用户 {current_user.username} 查找文件 '{pattern}'，找到 {len(matched_files)} 个文件"
    )
    return FileFindResponse(files=matched_files, total_count=len(matched_files))


@router.get("/files/search-keyword", response_model=FileKeywordSearchResponse)
def search_keyword_in_files(
    keyword: str,
    directory: str = ".",
    file_pattern: str = "*",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """搜索关键字，返回文件名和关键字所在行数（按文件分组）"""
    abs_dir = validate_path(directory)

    if not os.path.exists(abs_dir):
        raise HTTPException(status_code=404, detail="目录不存在")
    if not os.path.isdir(abs_dir):
        raise HTTPException(status_code=400, detail="路径不是目录")

    matches_by_file: dict[str, list[tuple[int, str]]] = {}

    for root, dirs, files in os.walk(abs_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

        for filename in files:
            if not fnmatch.fnmatch(filename, file_pattern):
                continue
            file_path = os.path.join(root, filename)
            if not is_text_file(file_path):
                continue

            try:
                lines = get_file_lines(file_path)
                for i, line in enumerate(lines):
                    if keyword in line:
                        rel_path = os.path.relpath(file_path, WORKSPACE_ROOT)
                        if rel_path not in matches_by_file:
                            matches_by_file[rel_path] = []
                        matches_by_file[rel_path].append(
                            (i + 1, line.rstrip("\n"))
                        )
            except Exception as e:
                logger.warning(f"搜索文件失败 {file_path}: {e}")
                continue

    matches = []
    total_matches = 0
    for file_path in sorted(matches_by_file.keys()):
        items = matches_by_file[file_path]
        line_numbers = [item[0] for item in items]
        preview_lines = [item[1] for item in items]
        total_matches += len(items)
        matches.append(
            FileKeywordMatch(
                file_path=file_path,
                line_numbers=line_numbers,
                preview_lines=preview_lines,
            )
        )

    logger.info(
        f"用户 {current_user.username} 搜索关键字 '{keyword}'，"
        f"在 {len(matches)} 个文件中找到 {total_matches} 个匹配"
    )
    return FileKeywordSearchResponse(
        keyword=keyword,
        matches=matches,
        total_files=len(matches),
        total_matches=total_matches,
    )


@router.get("/files/read", response_model=FileReadResponse)
def file_read(
    path: str = Query(..., description="文件路径"),
    start_line: Optional[int] = Query(None, ge=1, description="起始行号"),
    end_line: Optional[int] = Query(None, ge=1, description="结束行号"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    abs_path = validate_path(path)

    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    if os.path.isdir(abs_path):
        raise HTTPException(status_code=400, detail="路径是目录，不是文件")

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")

    total_lines = len(lines)

    if start_line is not None and end_line is not None:
        selected = lines[start_line - 1 : end_line]
    elif start_line is not None:
        selected = lines[start_line - 1 :]
    elif end_line is not None:
        selected = lines[:end_line]
    else:
        selected = lines

    content = "".join(selected)
    rel_path = os.path.relpath(abs_path, WORKSPACE_ROOT)

    logger.info(f"用户 {current_user.username} 读取文件 {rel_path}")
    return FileReadResponse(path=rel_path, content=content, total_lines=total_lines)


@router.post("/files/create", response_model=FileOperationResponse)
def file_create(
    req: FileCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    abs_path = validate_path(req.path)

    if os.path.exists(abs_path):
        raise HTTPException(status_code=400, detail="文件已存在")

    try:
        parent_dir = os.path.dirname(abs_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(req.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建文件失败: {str(e)}")

    rel_path = os.path.relpath(abs_path, WORKSPACE_ROOT)
    logger.info(f"用户 {current_user.username} 创建文件 {rel_path}")
    return FileOperationResponse(success=True, message="文件创建成功", path=rel_path)


@router.delete("/files/delete", response_model=FileOperationResponse)
def file_delete(
    path: str = Query(..., description="文件路径"),
    confirm: bool = Query(False, description="确认删除"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    abs_path = validate_path(path)

    if not confirm:
        raise HTTPException(status_code=400, detail="请设置 confirm=true 确认删除")

    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    if os.path.isdir(abs_path):
        raise HTTPException(status_code=400, detail="不能删除目录，仅支持删除文件")

    try:
        os.remove(abs_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")

    rel_path = os.path.relpath(abs_path, WORKSPACE_ROOT)
    logger.info(f"用户 {current_user.username} 删除文件 {rel_path}")
    return FileOperationResponse(success=True, message="文件删除成功", path=rel_path)


@router.put("/files/update", response_model=FileOperationResponse)
def file_update(
    req: FileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    abs_path = validate_path(req.path)

    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    if os.path.isdir(abs_path):
        raise HTTPException(status_code=400, detail="路径是目录，不是文件")

    try:
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(req.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新文件失败: {str(e)}")

    rel_path = os.path.relpath(abs_path, WORKSPACE_ROOT)
    logger.info(f"用户 {current_user.username} 更新文件 {rel_path}")
    return FileOperationResponse(success=True, message="文件更新成功", path=rel_path)


# ========== MCP工具端点 ==========

@router.get("/mcp/tools", response_model=McpToolListResponse)
def list_mcp_tools(current_user: User = Depends(get_current_user)):
    """列出所有可用的MCP工具"""
    # 返回预定义的工具列表元数据（描述文件操作和数据库工具的能力）
    tools = [
        McpToolInfo(
            name="file_search", description="全文检索文件内容",
            category="file_operations",
            parameters=[
                McpToolParameter(name="query", type="string", description="搜索关键词"),
                McpToolParameter(name="directory", type="string", description="搜索目录", required=False, default="."),
                McpToolParameter(name="file_pattern", type="string", description="文件名模式", required=False, default="*"),
            ]
        ),
        McpToolInfo(
            name="file_locate", description="按关键字定位文件内容并显示上下文",
            category="file_operations",
            parameters=[
                McpToolParameter(name="keyword", type="string", description="定位关键词"),
                McpToolParameter(name="directory", type="string", description="搜索目录", required=False, default="."),
                McpToolParameter(name="context_lines", type="int", description="上下文行数", required=False, default="3"),
            ]
        ),
        McpToolInfo(
            name="file_find", description="按名称模式查找文件",
            category="file_operations",
            parameters=[
                McpToolParameter(name="pattern", type="string", description="文件名匹配模式"),
                McpToolParameter(name="directory", type="string", description="搜索目录", required=False, default="."),
                McpToolParameter(name="use_regex", type="bool", description="是否使用正则表达式", required=False, default="false"),
            ]
        ),
        McpToolInfo(
            name="file_read", description="读取文件内容",
            category="file_operations",
            parameters=[
                McpToolParameter(name="path", type="string", description="文件路径"),
                McpToolParameter(name="start_line", type="int", description="起始行号", required=False),
                McpToolParameter(name="end_line", type="int", description="结束行号", required=False),
            ]
        ),
        McpToolInfo(
            name="file_create", description="创建新文件",
            category="file_operations",
            parameters=[
                McpToolParameter(name="path", type="string", description="文件路径"),
                McpToolParameter(name="content", type="string", description="文件内容", required=False, default=""),
            ],
            requires_confirmation=True
        ),
        McpToolInfo(
            name="file_delete", description="删除文件",
            category="file_operations",
            parameters=[
                McpToolParameter(name="path", type="string", description="文件路径"),
            ],
            requires_confirmation=True
        ),
        McpToolInfo(
            name="file_update", description="修改文件内容",
            category="file_operations",
            parameters=[
                McpToolParameter(name="path", type="string", description="文件路径"),
                McpToolParameter(name="content", type="string", description="新文件内容"),
            ],
            requires_confirmation=True
        ),
        McpToolInfo(
            name="db_test_connection", description="测试数据库连接",
            category="db_operations",
            parameters=[
                McpToolParameter(name="connection_id", type="int", description="数据库连接配置ID"),
            ]
        ),
        McpToolInfo(
            name="terminal_execute",
            description="在服务器终端执行命令",
            category="system",
            parameters=[
                McpToolParameter(name="command", type="string", description="要执行的终端命令"),
                McpToolParameter(name="working_directory", type="string", description="工作目录", required=False),
                McpToolParameter(name="timeout", type="int", description="超时时间(秒)", required=False, default="30"),
            ],
            requires_confirmation=True
        ),
        McpToolInfo(
            name="browser_navigate", description="导航到指定URL",
            category="browser",
            parameters=[
                McpToolParameter(name="url", type="string", description="目标URL"),
                McpToolParameter(name="wait_load", type="bool", description="是否等待页面加载完成", required=False, default="true"),
            ],
            requires_confirmation=True
        ),
        McpToolInfo(
            name="browser_screenshot", description="截取当前页面截图",
            category="browser",
            parameters=[
                McpToolParameter(name="full_page", type="bool", description="是否截取完整页面", required=False, default="false"),
            ],
            requires_confirmation=True
        ),
        McpToolInfo(
            name="browser_click", description="点击页面元素",
            category="browser",
            parameters=[
                McpToolParameter(name="selector", type="string", description="CSS选择器"),
                McpToolParameter(name="wait_after", type="int", description="点击后等待秒数", required=False, default="1"),
            ],
            requires_confirmation=True
        ),
        McpToolInfo(
            name="browser_type", description="在输入框中输入文本",
            category="browser",
            parameters=[
                McpToolParameter(name="selector", type="string", description="CSS选择器"),
                McpToolParameter(name="text", type="string", description="要输入的文本"),
            ],
            requires_confirmation=True
        ),
        McpToolInfo(
            name="browser_extract", description="提取页面内容",
            category="browser",
            parameters=[
                McpToolParameter(name="selector", type="string", description="CSS选择器(为空则提取整个页面)", required=False),
            ],
            requires_confirmation=True
        ),
    ]
    return McpToolListResponse(tools=tools, total_count=len(tools))


@router.post("/mcp/execute", response_model=McpExecuteResponse)
def execute_mcp_tool(
    request: McpExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """通过MCP协议执行工具"""
    import time
    start_time = time.time()

    tool_name = request.tool_name
    params = request.parameters

    try:
        # 根据工具名称路由到对应的实现
        if tool_name == "file_search":
            # 复用文件搜索逻辑
            from schemas.toolbox import FileSearchRequest
            search_req = FileSearchRequest(**params)
            result = _execute_file_search(search_req)
        elif tool_name == "file_locate":
            from schemas.toolbox import FileLocateRequest
            locate_req = FileLocateRequest(**params)
            result = _execute_file_locate(locate_req)
        elif tool_name == "file_find":
            result = _execute_file_find(params)
        elif tool_name == "file_read":
            result = _execute_file_read(params)
        elif tool_name == "file_create":
            from schemas.toolbox import FileCreateRequest
            create_req = FileCreateRequest(**params)
            result = _execute_file_create(create_req)
        elif tool_name == "file_delete":
            result = _execute_file_delete(params)
        elif tool_name == "file_update":
            from schemas.toolbox import FileUpdateRequest
            update_req = FileUpdateRequest(**params)
            result = _execute_file_update(update_req)
        elif tool_name == "db_test_connection":
            result = _execute_db_test(params, db, current_user)
        elif tool_name == "terminal_execute":
            result = _execute_terminal(params)
        elif tool_name in ("browser_navigate", "browser_screenshot", "browser_click", "browser_type", "browser_extract"):
            result = _execute_browser_action(tool_name, params)
        else:
            raise HTTPException(status_code=404, detail=f"未知工具: {tool_name}")

        elapsed = (time.time() - start_time) * 1000
        return McpExecuteResponse(success=True, tool_name=tool_name, result=result, execution_time_ms=round(elapsed, 2))
    except HTTPException:
        raise
    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        logger.error(f"MCP工具执行失败 [{tool_name}]: {str(e)}")
        return McpExecuteResponse(success=False, tool_name=tool_name, error=str(e), execution_time_ms=round(elapsed, 2))


# ========== MCP工具内部辅助函数 ==========

def _execute_file_search(search_req):
    """执行文件搜索"""
    directory = validate_path(search_req.directory)

    if not os.path.exists(directory):
        raise HTTPException(status_code=404, detail="目录不存在")
    if not os.path.isdir(directory):
        raise HTTPException(status_code=400, detail="路径不是目录")

    matches = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

        for filename in files:
            if not fnmatch.fnmatch(filename, search_req.file_pattern):
                continue
            file_path = os.path.join(root, filename)
            if not is_text_file(file_path):
                continue

            try:
                lines = get_file_lines(file_path)
                for i, line in enumerate(lines):
                    if search_req.query in line:
                        context_before = [
                            l.rstrip("\n") for l in lines[max(0, i - 2) : i]
                        ]
                        context_after = [
                            l.rstrip("\n")
                            for l in lines[i + 1 : min(len(lines), i + 3)]
                        ]
                        rel_path = os.path.relpath(file_path, WORKSPACE_ROOT)
                        matches.append(
                            FileSearchMatch(
                                file_path=rel_path,
                                line_number=i + 1,
                                line_content=line.rstrip("\n"),
                                context_before=context_before,
                                context_after=context_after,
                            )
                        )
            except Exception as e:
                logger.warning(f"搜索文件失败 {file_path}: {e}")
                continue

    return {"matches": [m.model_dump() for m in matches], "total_count": len(matches)}


def _execute_file_locate(locate_req):
    """执行文件定位"""
    directory = validate_path(locate_req.directory)

    if not os.path.exists(directory):
        raise HTTPException(status_code=404, detail="目录不存在")
    if not os.path.isdir(directory):
        raise HTTPException(status_code=400, detail="路径不是目录")

    results = []
    context = locate_req.context_lines

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

        for filename in files:
            file_path = os.path.join(root, filename)
            if not is_text_file(file_path):
                continue

            try:
                lines = get_file_lines(file_path)
                for i, line in enumerate(lines):
                    if locate_req.keyword in line:
                        rel_path = os.path.relpath(file_path, WORKSPACE_ROOT)
                        start = max(0, i - context)
                        end = min(len(lines), i + context + 1)
                        context_lines = [l.rstrip("\n") for l in lines[start:end]]
                        highlighted = [
                            f">> {l} <<" if idx == i - start else l
                            for idx, l in enumerate(context_lines)
                        ]
                        results.append(
                            {
                                "file_path": rel_path,
                                "line_number": i + 1,
                                "line_content": line.rstrip("\n"),
                                "context": highlighted,
                            }
                        )
            except Exception as e:
                logger.warning(f"定位文件失败 {file_path}: {e}")
                continue

    return {"matches": results, "total_count": len(results)}


def _execute_file_find(params):
    """执行文件查找"""
    directory = validate_path(params.get("directory", "."))
    pattern = params.get("pattern", "")
    use_regex = params.get("use_regex", False)

    if not os.path.exists(directory):
        raise HTTPException(status_code=404, detail="目录不存在")
    if not os.path.isdir(directory):
        raise HTTPException(status_code=400, detail="路径不是目录")

    matched_files = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

        for filename in files:
            if use_regex:
                if re.search(pattern, filename):
                    matched_files.append(
                        os.path.relpath(os.path.join(root, filename), WORKSPACE_ROOT)
                    )
            else:
                if fnmatch.fnmatch(filename, pattern):
                    matched_files.append(
                        os.path.relpath(os.path.join(root, filename), WORKSPACE_ROOT)
                    )

    return {"files": matched_files, "total_count": len(matched_files)}


def _execute_file_read(params):
    """执行文件读取"""
    path = params.get("path", "")
    start_line = params.get("start_line")
    end_line = params.get("end_line")

    abs_path = validate_path(path)

    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    if os.path.isdir(abs_path):
        raise HTTPException(status_code=400, detail="路径是目录，不是文件")

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")

    total_lines = len(lines)

    if start_line is not None and end_line is not None:
        selected = lines[start_line - 1 : end_line]
    elif start_line is not None:
        selected = lines[start_line - 1 :]
    elif end_line is not None:
        selected = lines[:end_line]
    else:
        selected = lines

    content = "".join(selected)
    rel_path = os.path.relpath(abs_path, WORKSPACE_ROOT)

    return {"path": rel_path, "content": content, "total_lines": total_lines}


def _execute_file_create(create_req):
    """执行文件创建"""
    abs_path = validate_path(create_req.path)

    if os.path.exists(abs_path):
        raise HTTPException(status_code=400, detail="文件已存在")

    try:
        parent_dir = os.path.dirname(abs_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(create_req.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建文件失败: {str(e)}")

    rel_path = os.path.relpath(abs_path, WORKSPACE_ROOT)
    return {"success": True, "message": "文件创建成功", "path": rel_path}


def _execute_file_delete(params):
    """执行文件删除"""
    path = params.get("path", "")
    abs_path = validate_path(path)

    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    if os.path.isdir(abs_path):
        raise HTTPException(status_code=400, detail="不能删除目录，仅支持删除文件")

    try:
        os.remove(abs_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")

    rel_path = os.path.relpath(abs_path, WORKSPACE_ROOT)
    return {"success": True, "message": "文件删除成功", "path": rel_path}


def _execute_file_update(update_req):
    """执行文件更新"""
    abs_path = validate_path(update_req.path)

    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    if os.path.isdir(abs_path):
        raise HTTPException(status_code=400, detail="路径是目录，不是文件")

    try:
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(update_req.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新文件失败: {str(e)}")

    rel_path = os.path.relpath(abs_path, WORKSPACE_ROOT)
    return {"success": True, "message": "文件更新成功", "path": rel_path}


def _execute_db_test(params, db, current_user):
    """测试数据库连接"""
    from models.db_connection import DbConnection
    conn_id = params.get("connection_id")
    conn = db.query(DbConnection).filter(DbConnection.id == conn_id, DbConnection.user_id == current_user.id).first()
    if not conn:
        return {"success": False, "message": "连接配置不存在"}
    import socket, time
    start = time.time()
    try:
        sock = socket.create_connection((conn.host, conn.port), timeout=5)
        sock.close()
        latency = (time.time() - start) * 1000
        return {"success": True, "message": "连接成功", "latency_ms": round(latency, 2)}
    except Exception as e:
        return {"success": False, "message": f"连接失败: {str(e)}"}


def _execute_terminal(params: dict) -> dict:
    """执行终端命令"""
    import subprocess
    import time

    command = params.get("command")
    if not command:
        return {"success": False, "exit_code": -1, "stdout": "", "stderr": "命令不能为空", "execution_time_ms": 0}

    working_dir = params.get("working_directory")
    if working_dir:
        working_dir = validate_path(working_dir)
        if not os.path.isdir(working_dir):
            return {"success": False, "exit_code": -1, "stdout": "", "stderr": "工作目录不存在", "execution_time_ms": 0}
    else:
        working_dir = WORKSPACE_ROOT

    timeout = min(params.get("timeout", 30), 120)  # 最大120秒

    # 安全检查：禁止危险命令
    dangerous_commands = ["rm -rf /", "mkfs", "dd if=", ":(){:|:&};:", "fork bomb"]
    for dc in dangerous_commands:
        if dc in command:
            return {"success": False, "exit_code": -1, "stdout": "", "stderr": f"禁止执行危险命令: {command}", "execution_time_ms": 0}

    start_time = time.time()
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir
        )
        elapsed = (time.time() - start_time) * 1000
        return {
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout[:10000],  # 限制输出大小
            "stderr": result.stderr[:5000],
            "execution_time_ms": round(elapsed, 2)
        }
    except subprocess.TimeoutExpired:
        elapsed = (time.time() - start_time) * 1000
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"命令执行超时({timeout}秒)",
            "execution_time_ms": round(elapsed, 2)
        }
    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "execution_time_ms": round(elapsed, 2)
        }


# ========== 终端操控端点 ==========

@router.post("/terminal/execute")
def execute_terminal_command(
    request: TerminalExecuteRequest,
    current_user: User = Depends(get_current_user)
):
    """直接执行终端命令"""
    result = _execute_terminal({
        "command": request.command,
        "working_directory": request.working_directory,
        "timeout": request.timeout
    })
    logger.info(f"用户 {current_user.username} 执行终端命令: {request.command}")
    return result


# ========== 智能体任务关联端点 ==========

@router.post("/agent-task", response_model=AgentTaskResponse)
def suggest_agent_task(
    request: AgentTaskSuggestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI建议创建任务（状态为pending_confirmation）"""
    from models.agent import Agent
    from models.task import Task

    # 验证智能体存在
    agent = db.query(Agent).filter(Agent.id == request.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")

    # 创建任务（状态为pending，需确认后才执行）
    task = Task(
        name=request.task_name,
        description=request.task_description,
        agent_id=request.agent_id,
        status="pending",
        priority=request.priority,
        result=request.parameters
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    return AgentTaskResponse(
        id=task.id, agent_id=task.agent_id, task_name=task.name,
        task_description=task.description or "", status="pending_confirmation",
        priority=task.priority or 0, parameters=request.parameters,
        created_at=task.created_at, updated_at=task.updated_at
    )


@router.put("/agent-task/{task_id}/confirm", response_model=AgentTaskResponse)
def confirm_agent_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """用户确认执行任务"""
    from models.task import Task
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    task.status = "pending"  # 设为待执行
    db.commit()
    db.refresh(task)
    return _task_to_response(task)


@router.put("/agent-task/{task_id}/modify", response_model=AgentTaskResponse)
def modify_agent_task(task_id: int, request: AgentTaskModifyRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """通过对话修改任务参数"""
    from models.task import Task
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if request.task_name: task.name = request.task_name
    if request.task_description: task.description = request.task_description
    if request.priority is not None: task.priority = request.priority
    if request.parameters: task.result = request.parameters
    db.commit()
    db.refresh(task)
    return _task_to_response(task)


@router.get("/agent-task/{task_id}/status", response_model=AgentTaskStatusResponse)
def get_agent_task_status(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取任务实时状态"""
    from models.task import Task
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return AgentTaskStatusResponse(
        id=task.id, status=task.status,
        execution_log=task.execution_log, result=task.result
    )


def _task_to_response(task) -> AgentTaskResponse:
    return AgentTaskResponse(
        id=task.id, agent_id=task.agent_id or 0,
        task_name=task.name, task_description=task.description or "",
        status=task.status, priority=task.priority or 0,
        parameters=task.result, created_at=task.created_at, updated_at=task.updated_at
    )


# ========== Browser-Use 浏览器操控 ==========

import threading

class BrowserManager:
    """单例浏览器管理器，维持一个浏览器实例"""
    _instance = None
    _lock = threading.Lock()
    _browser = None
    _page = None
    _playwright = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _ensure_browser(self):
        """确保浏览器实例存在"""
        if self._browser is None or not self._browser.is_connected():
            try:
                from playwright.sync_api import sync_playwright
                self._playwright = sync_playwright().start()
                self._browser = self._playwright.chromium.launch(headless=True)
                context = self._browser.new_context(viewport={"width": 1280, "height": 720})
                self._page = context.new_page()
                logger.info("Browser instance started")
            except ImportError:
                logger.error("playwright 未安装，请执行: pip install playwright>=1.40.0 && playwright install chromium")
                raise HTTPException(status_code=500, detail="playwright 未安装，无法启动浏览器")
            except Exception as e:
                logger.error(f"Failed to start browser: {e}")
                raise

    def get_page(self):
        self._ensure_browser()
        return self._page

    def close(self):
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except:
            pass
        self._browser = None
        self._page = None
        self._playwright = None


def _execute_browser_action(action: str, params: dict) -> dict:
    """执行浏览器操作"""
    import base64

    try:
        manager = BrowserManager.get_instance()
        page = manager.get_page()

        if action == "browser_navigate":
            url = params.get("url", "")
            if not url:
                return {"success": False, "message": "URL不能为空"}
            wait_load = params.get("wait_load", True)
            wait_until = "load" if wait_load else "commit"
            page.goto(url, wait_until=wait_until, timeout=30000)
            return {
                "success": True,
                "message": f"已导航到 {url}",
                "data": {"url": page.url, "title": page.title()}
            }

        elif action == "browser_screenshot":
            full_page = params.get("full_page", False)
            screenshot_bytes = page.screenshot(full_page=full_page)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            return {
                "success": True,
                "message": "截图成功",
                "data": {"screenshot": screenshot_b64, "url": page.url, "title": page.title()}
            }

        elif action == "browser_click":
            selector = params.get("selector", "")
            if not selector:
                return {"success": False, "message": "选择器不能为空"}
            wait_after = params.get("wait_after", 1)
            page.click(selector, timeout=10000)
            if wait_after > 0:
                page.wait_for_timeout(wait_after * 1000)
            return {
                "success": True,
                "message": f"已点击元素: {selector}",
                "data": {"url": page.url, "title": page.title()}
            }

        elif action == "browser_type":
            selector = params.get("selector", "")
            text = params.get("text", "")
            if not selector or not text:
                return {"success": False, "message": "选择器和文本不能为空"}
            page.fill(selector, text, timeout=10000)
            return {
                "success": True,
                "message": f"已在 {selector} 中输入文本",
                "data": {"selector": selector, "text_length": len(text)}
            }

        elif action == "browser_extract":
            selector = params.get("selector")
            if selector:
                elements = page.query_selector_all(selector)
                texts = [el.text_content() or "" for el in elements]
                return {
                    "success": True,
                    "message": f"已提取 {len(texts)} 个元素的内容",
                    "data": {"extracted_texts": texts, "count": len(texts)}
                }
            else:
                content = page.content()
                text = page.evaluate("() => document.body.innerText")
                return {
                    "success": True,
                    "message": "已提取整个页面内容",
                    "data": {"text": text[:10000], "url": page.url, "title": page.title()}
                }

        return {"success": False, "message": f"未知浏览器操作: {action}"}

    except Exception as e:
        logger.error(f"Browser action failed [{action}]: {str(e)}")
        return {"success": False, "message": f"浏览器操作失败: {str(e)}"}


# ========== 浏览器操控独立 REST 端点 ==========

@router.post("/browser/navigate")
def browser_navigate(request: BrowserNavigateRequest, current_user: User = Depends(get_current_user)):
    """浏览器导航到URL"""
    return _execute_browser_action("browser_navigate", {"url": request.url, "wait_load": request.wait_load})

@router.post("/browser/screenshot")
def browser_screenshot(request: BrowserScreenshotRequest, current_user: User = Depends(get_current_user)):
    """截取浏览器截图"""
    return _execute_browser_action("browser_screenshot", {"full_page": request.full_page})

@router.post("/browser/click")
def browser_click(request: BrowserClickRequest, current_user: User = Depends(get_current_user)):
    """点击页面元素"""
    return _execute_browser_action("browser_click", {"selector": request.selector, "wait_after": request.wait_after})

@router.post("/browser/type")
def browser_type(request: BrowserTypeRequest, current_user: User = Depends(get_current_user)):
    """输入文本"""
    return _execute_browser_action("browser_type", {"selector": request.selector, "text": request.text})

@router.post("/browser/extract")
def browser_extract(request: BrowserExtractRequest, current_user: User = Depends(get_current_user)):
    """提取页面内容"""
    return _execute_browser_action("browser_extract", {"selector": request.selector})


# ========== 目录浏览端点 ==========

@router.get("/directories/browse")
async def browse_directories(
    path: str = Query(default="~"),
    current_user: User = Depends(get_current_user),
):
    """浏览服务器目录结构"""
    target = os.path.expanduser(path)
    if not os.path.isdir(target):
        raise HTTPException(status_code=400, detail="路径不存在或不是目录")

    items = []
    try:
        for name in sorted(os.listdir(target)):
            full_path = os.path.join(target, name)
            if os.path.isdir(full_path) and not name.startswith("."):
                items.append({
                    "name": name,
                    "path": full_path,
                    "type": "directory",
                })
    except PermissionError:
        raise HTTPException(status_code=403, detail="无权限访问此目录")

    return {
        "current_path": target,
        "parent_path": os.path.dirname(target),
        "directories": items,
    }
