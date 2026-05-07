"""
ToolRegistry 测试
"""

import pytest
import os
import json
from core.tool_registry import ToolRegistry, Tool, ToolCategory, reset_tool_registry


@pytest.fixture
def registry(tmp_path):
    """创建带临时目录的工具注册表"""
    reset_tool_registry()
    return ToolRegistry(str(tmp_path))


def test_builtin_tools_registered(registry):
    """测试内置工具已注册"""
    tools = registry.list_tools()
    names = [t.name for t in tools]
    assert "file_read" in names
    assert "file_create" in names
    assert "file_update" in names
    assert "file_delete" in names
    assert "file_search" in names
    assert "file_find" in names
    assert "terminal_execute" in names


def test_tools_by_category(registry):
    """测试按类别过滤工具"""
    file_tools = registry.list_tools(ToolCategory.FILE)
    assert all(t.category == ToolCategory.FILE for t in file_tools)

    search_tools = registry.list_tools(ToolCategory.SEARCH)
    assert all(t.category == ToolCategory.SEARCH for t in search_tools)


def test_register_custom_tool(registry):
    """测试注册自定义工具"""
    def my_tool(x: str) -> str:
        return f"result: {x}"

    tool = Tool(
        name="my_tool",
        description="测试工具",
        category=ToolCategory.SYSTEM,
        func=my_tool,
        parameters={"x": "str"},
    )
    registry.register(tool)

    assert registry.get("my_tool") is not None
    assert registry.get("my_tool").description == "测试工具"


def test_file_create_and_read(registry, tmp_path):
    """测试文件创建和读取"""
    result = registry.get("file_create").func(path="test.txt", content="hello world")
    data = json.loads(result)
    assert data["success"]

    content = registry.get("file_read").func(path="test.txt")
    assert content == "hello world"


def test_file_create_prevents_overwrite(registry, tmp_path):
    """测试文件创建防止覆盖"""
    registry.get("file_create").func(path="test.txt", content="original")
    result = registry.get("file_create").func(path="test.txt", content="new")
    data = json.loads(result)
    assert "error" in data


def test_file_update(registry, tmp_path):
    """测试文件更新"""
    registry.get("file_create").func(path="test.txt", content="original")
    result = registry.get("file_update").func(path="test.txt", content="updated")
    data = json.loads(result)
    assert data["success"]

    content = registry.get("file_read").func(path="test.txt")
    assert content == "updated"


def test_file_delete(registry, tmp_path):
    """测试文件删除"""
    registry.get("file_create").func(path="test.txt", content="delete me")
    result = registry.get("file_delete").func(path="test.txt", confirm=True)
    data = json.loads(result)
    assert data["success"]

    # 验证已删除
    content = registry.get("file_read").func(path="test.txt")
    assert "读取错误" in content


def test_file_delete_requires_confirm(registry, tmp_path):
    """测试删除需要确认"""
    registry.get("file_create").func(path="test.txt", content="content")
    result = registry.get("file_delete").func(path="test.txt", confirm=False)
    data = json.loads(result)
    assert "error" in data


def test_file_search(registry, tmp_path):
    """测试文件搜索"""
    registry.get("file_create").func(path="a.txt", content="hello world\nfoo bar")
    registry.get("file_create").func(path="b.txt", content="baz\nhello again")

    result = registry.get("file_search").func(query="hello")
    data = json.loads(result)
    assert data["total"] == 2


def test_file_find(registry, tmp_path):
    """测试文件名搜索"""
    registry.get("file_create").func(path="test.py", content="print(1)")
    registry.get("file_create").func(path="test.txt", content="hello")

    result = registry.get("file_find").func(pattern="*.py")
    data = json.loads(result)
    assert "test.py" in data["files"]
    assert "test.txt" not in data["files"]


def test_path_validation_prevents_escape(registry, tmp_path):
    """测试路径安全验证阻止目录逃逸"""
    result = registry.get("file_read").func(path="../../../etc/passwd")
    assert "读取错误" in result or "不在允许" in result


def test_terminal_execute(registry, tmp_path):
    """测试终端命令执行"""
    result = registry.get("terminal_execute").func(command="echo hello")
    data = json.loads(result)
    assert data["exit_code"] == 0
    assert "hello" in data["stdout"]


def test_terminal_blocks_dangerous_commands(registry):
    """测试危险命令拦截"""
    result = registry.get("terminal_execute").func(command="rm -rf /")
    data = json.loads(result)
    assert "error" in data


def test_workspace_update(registry, tmp_path):
    """测试工作目录更新"""
    new_dir = tmp_path / "new_workspace"
    new_dir.mkdir()
    registry.set_workspace(str(new_dir))
    assert registry.workspace_root == str(new_dir)
