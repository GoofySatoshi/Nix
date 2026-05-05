import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# 记忆分类
class MemoryCategory:
    USER_PREFERENCE = "用户偏好"
    PROJECT_RULE = "项目规则"
    PROJECT_SPEC = "项目规范"
    WORK_EXPERIENCE = "工作经验"
    TOOL_USAGE = "工具使用经验"
    ERROR_LESSON = "错误教训"

MEMORY_CATEGORIES = [
    MemoryCategory.USER_PREFERENCE,
    MemoryCategory.PROJECT_RULE,
    MemoryCategory.PROJECT_SPEC,
    MemoryCategory.WORK_EXPERIENCE,
    MemoryCategory.TOOL_USAGE,
    MemoryCategory.ERROR_LESSON,
]

# 项目级记忆分类（存在 .nix/project-memory.md）
PROJECT_CATEGORIES = [
    MemoryCategory.PROJECT_RULE,
    MemoryCategory.PROJECT_SPEC,
]

# 智能体级记忆分类（存在 skills/{agent}-SOUL.md）
AGENT_CATEGORIES = [
    MemoryCategory.USER_PREFERENCE,
    MemoryCategory.WORK_EXPERIENCE,
    MemoryCategory.TOOL_USAGE,
    MemoryCategory.ERROR_LESSON,
]


def get_skills_root() -> str:
    """获取 skills 根目录"""
    logger.info("[MemoryService.get_skills_root] 入参: 无")
    result = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "skills"
    )
    logger.info(f"[MemoryService.get_skills_root] 返回: {result}")
    return result


def get_soul_file_path(agent_name: str) -> str:
    """获取智能体灵魂记忆文件路径"""
    logger.info(f"[MemoryService.get_soul_file_path] 入参: agent_name={agent_name}")
    skills_root = get_skills_root()
    safe_name = agent_name.replace("/", "_").replace("\\", "_").replace("..", "_")
    result = os.path.join(skills_root, f"{safe_name}-SOUL.md")
    logger.info(f"[MemoryService.get_soul_file_path] 返回: {result}")
    return result


def read_soul_memory(agent_name: str) -> Dict:
    """读取智能体灵魂记忆"""
    logger.info(f"[MemoryService.read_soul_memory] 入参: agent_name={agent_name}")
    file_path = get_soul_file_path(agent_name)
    if not os.path.exists(file_path):
        return {
            "agent_name": agent_name,
            "memories": [],
            "raw_content": "",
            "last_updated": None,
        }

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 解析 markdown 格式的记忆
    memories = parse_soul_markdown(content)

    return {
        "agent_name": agent_name,
        "memories": memories,
        "raw_content": content,
        "last_updated": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
    }


def parse_soul_markdown(content: str) -> List[Dict]:
    """解析 SOUL.md 格式，提取结构化记忆条目"""
    logger.info(f"[MemoryService.parse_soul_markdown] 入参: content长度={len(content) if content else 0}")
    memories = []
    current_category = ""
    current_items = []

    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("## "):
            # 保存上一个分类的条目
            if current_category and current_items:
                for item in current_items:
                    memories.append({
                        "category": current_category,
                        "content": item,
                    })
            current_category = line[3:].strip()
            current_items = []
        elif line.startswith("- ") and current_category:
            current_items.append(line[2:].strip())
        elif line and current_category and not line.startswith("#"):
            # 多行内容追加到最后一个条目
            if current_items:
                current_items[-1] += "\n" + line
            else:
                current_items.append(line)

    # 别忘了最后一个分类
    if current_category and current_items:
        for item in current_items:
            memories.append({
                "category": current_category,
                "content": item,
            })

    logger.info(f"[MemoryService.parse_soul_markdown] 返回: {len(memories)} 条记忆")
    return memories


def write_soul_memory(agent_name: str, memories: List[Dict]) -> str:
    """将结构化记忆写入 SOUL.md 文件"""
    logger.info(f"[MemoryService.write_soul_memory] 入参: agent_name={agent_name}, memories数={len(memories)}")
    file_path = get_soul_file_path(agent_name)
    skills_root = get_skills_root()
    os.makedirs(skills_root, exist_ok=True)

    # 按分类组织
    categorized = {}
    for mem in memories:
        cat = mem.get("category", "未分类")
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append(mem.get("content", ""))

    # 生成 markdown
    lines = [f"# {agent_name} 灵魂记忆\n"]
    lines.append(f"> 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 按固定顺序排列分类
    ordered_cats = [c for c in MEMORY_CATEGORIES if c in categorized]
    remaining_cats = [c for c in categorized if c not in ordered_cats]

    for cat in ordered_cats + remaining_cats:
        items = categorized[cat]
        lines.append(f"\n## {cat}\n")
        for item in items:
            lines.append(f"- {item}")

    content = "\n".join(lines) + "\n"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"[MemoryService.write_soul_memory] 返回: {file_path}")
    return file_path


def get_project_memory_path(workspace: str = None) -> str:
    """获取项目级记忆文件路径"""
    logger.info(f"[MemoryService.get_project_memory_path] 入参: workspace={workspace}")
    if workspace and workspace != ".":
        nix_dir = os.path.join(workspace, ".nix")
    else:
        # 默认使用项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        nix_dir = os.path.join(project_root, ".nix")

    os.makedirs(nix_dir, exist_ok=True)
    result = os.path.join(nix_dir, "project-memory.md")
    logger.info(f"[MemoryService.get_project_memory_path] 返回: {result}")
    return result


def read_project_memory(workspace: str = None) -> Dict:
    """读取项目级记忆"""
    logger.info(f"[MemoryService.read_project_memory] 入参: workspace={workspace}")
    file_path = get_project_memory_path(workspace)
    if not os.path.exists(file_path):
        return {
            "memories": [],
            "raw_content": "",
            "last_updated": None,
        }

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    memories = parse_soul_markdown(content)
    # 只返回项目级分类的记忆
    memories = [m for m in memories if m["category"] in PROJECT_CATEGORIES]

    return {
        "memories": memories,
        "raw_content": content,
        "last_updated": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
    }


def write_project_memory(memories: List[Dict], workspace: str = None) -> str:
    """将项目级记忆写入 .nix/project-memory.md"""
    logger.info(f"[MemoryService.write_project_memory] 入参: memories数={len(memories)}, workspace={workspace}")
    file_path = get_project_memory_path(workspace)

    categorized = {}
    for mem in memories:
        cat = mem.get("category", "未分类")
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append(mem.get("content", ""))

    lines = ["# 项目记忆\n"]
    lines.append(f"> 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("> 此文件由 Nix 自动管理，存储项目级的规则和规范\n")

    for cat in PROJECT_CATEGORIES:
        if cat in categorized:
            lines.append(f"\n## {cat}\n")
            for item in categorized[cat]:
                lines.append(f"- {item}")

    content = "\n".join(lines) + "\n"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"[MemoryService.write_project_memory] 返回: {file_path}")
    return file_path


def add_memory(agent_name: str, category: str, content: str, workspace: str = None) -> Dict:
    """添加一条记忆（自动路由到项目级或智能体级）"""
    logger.info(f"[MemoryService.add_memory] 入参: agent_name={agent_name}, category={category}, content={content[:50]}, workspace={workspace}")
    if category in PROJECT_CATEGORIES:
        data = read_project_memory(workspace)
        memories = data["memories"]
        # 检查重复
        for mem in memories:
            if mem["category"] == category and mem["content"].strip() == content.strip():
                return {"success": False, "message": "该记忆已存在"}
        memories.append({"category": category, "content": content})
        write_project_memory(memories, workspace)
        logger.info("[MemoryService.add_memory] 返回: 项目记忆已添加")
        return {"success": True, "message": "项目记忆已添加"}
    else:
        # 智能体级（原有逻辑）
        data = read_soul_memory(agent_name)
        memories = data["memories"]
        for mem in memories:
            if mem["category"] == category and mem["content"].strip() == content.strip():
                return {"success": False, "message": "该记忆已存在"}
        memories.append({"category": category, "content": content})
        write_soul_memory(agent_name, memories)
        logger.info("[MemoryService.add_memory] 返回: 智能体记忆已添加")
        return {"success": True, "message": "智能体记忆已添加"}


def delete_memory(agent_name: str, category: str, content: str, workspace: str = None) -> Dict:
    """删除一条记忆"""
    logger.info(f"[MemoryService.delete_memory] 入参: agent_name={agent_name}, category={category}, content={content[:50]}, workspace={workspace}")
    if category in PROJECT_CATEGORIES:
        data = read_project_memory(workspace)
        memories = data["memories"]
        new_memories = [m for m in memories if not (m["category"] == category and m["content"].strip() == content.strip())]
        if len(new_memories) == len(memories):
            return {"success": False, "message": "未找到匹配的记忆"}
        write_project_memory(new_memories, workspace)
        return {"success": True, "message": "项目记忆已删除"}
    else:
        data = read_soul_memory(agent_name)
        memories = data["memories"]
        new_memories = [m for m in memories if not (m["category"] == category and m["content"].strip() == content.strip())]
        if len(new_memories) == len(memories):
            return {"success": False, "message": "未找到匹配的记忆"}
        write_soul_memory(agent_name, new_memories)
        return {"success": True, "message": "智能体记忆已删除"}


def update_memory(agent_name: str, category: str, old_content: str, new_content: str, workspace: str = None) -> Dict:
    """更新一条记忆"""
    logger.info(f"[MemoryService.update_memory] 入参: agent_name={agent_name}, category={category}, old_content={old_content[:50]}, new_content={new_content[:50]}, workspace={workspace}")
    if category in PROJECT_CATEGORIES:
        data = read_project_memory(workspace)
        memories = data["memories"]
        found = False
        for mem in memories:
            if mem["category"] == category and mem["content"].strip() == old_content.strip():
                mem["content"] = new_content
                found = True
                break
        if not found:
            return {"success": False, "message": "未找到匹配的记忆"}
        write_project_memory(memories, workspace)
        return {"success": True, "message": "项目记忆已更新"}
    else:
        data = read_soul_memory(agent_name)
        memories = data["memories"]
        found = False
        for mem in memories:
            if mem["category"] == category and mem["content"].strip() == old_content.strip():
                mem["content"] = new_content
                found = True
                break
        if not found:
            return {"success": False, "message": "未找到匹配的记忆"}
        write_soul_memory(agent_name, memories)
        return {"success": True, "message": "智能体记忆已更新"}


def get_full_memory_for_agent(agent_name: str, workspace: str = None) -> List[Dict]:
    """获取智能体的完整记忆（项目级 + 智能体级合并）"""
    logger.info(f"[MemoryService.get_full_memory_for_agent] 入参: agent_name={agent_name}, workspace={workspace}")
    all_memories = []

    # 项目级记忆
    project_data = read_project_memory(workspace)
    all_memories.extend(project_data["memories"])

    # 智能体级记忆
    agent_data = read_soul_memory(agent_name)
    all_memories.extend(agent_data["memories"])

    logger.info(f"[MemoryService.get_full_memory_for_agent] 返回: {len(all_memories)} 条记忆")
    return all_memories
