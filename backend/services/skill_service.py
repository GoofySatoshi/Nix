import os
import re
import yaml
from typing import Optional


def parse_skill_file(file_path: str) -> Optional[dict]:
    """解析 .nix/skills/ 下的 Markdown skill 文件
    
    格式：
    ---
    name: 技能名
    description: 描述
    keywords: [kw1, kw2]
    category: 分类
    ---
    正文内容（Markdown）
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 解析 YAML front-matter
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
        if not match:
            # 无 front-matter，整个文件作为 content
            name = os.path.splitext(os.path.basename(file_path))[0]
            return {
                "name": name,
                "description": "",
                "keywords": [],
                "category": "general",
                "content": content.strip(),
            }
        
        front_matter = yaml.safe_load(match.group(1))
        body = match.group(2).strip()
        
        return {
            "name": front_matter.get("name", os.path.splitext(os.path.basename(file_path))[0]),
            "description": front_matter.get("description", ""),
            "keywords": front_matter.get("keywords", []),
            "category": front_matter.get("category", "general"),
            "content": body,
        }
    except Exception:
        return None


def write_skill_file(workspace: str, name: str, description: str, 
                     keywords: list, category: str, content: str) -> str:
    """写入项目级 Skill 文件到 .nix/skills/ 目录
    
    返回文件路径
    """
    skills_dir = os.path.join(workspace, ".nix", "skills")
    os.makedirs(skills_dir, exist_ok=True)
    
    # 文件名安全处理
    safe_name = re.sub(r'[^\w\u4e00-\u9fff\-]', '_', name)
    file_path = os.path.join(skills_dir, f"{safe_name}.md")
    
    front_matter = {
        "name": name,
        "description": description,
        "keywords": keywords,
        "category": category,
    }
    
    file_content = f"""---
{yaml.dump(front_matter, allow_unicode=True, default_flow_style=False).strip()}
---

{content}
"""
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(file_content)
    
    return file_path


def load_nix_skill_files(workspace: str) -> list[dict]:
    """加载工作目录 .nix/skills/ 下所有 skill 文件"""
    skills_dir = os.path.join(workspace, ".nix", "skills")
    if not os.path.isdir(skills_dir):
        return []
    
    skills = []
    for filename in os.listdir(skills_dir):
        if filename.endswith('.md'):
            file_path = os.path.join(skills_dir, filename)
            skill = parse_skill_file(file_path)
            if skill:
                skill["scope"] = "project"
                skill["source"] = "file"
                skills.append(skill)
    
    return skills


def delete_skill_file(workspace: str, name: str) -> bool:
    """删除项目级 Skill 文件"""
    skills_dir = os.path.join(workspace, ".nix", "skills")
    safe_name = re.sub(r'[^\w\u4e00-\u9fff\-]', '_', name)
    file_path = os.path.join(skills_dir, f"{safe_name}.md")
    if os.path.exists(file_path):
        os.remove(file_path)
        return True
    return False


def load_relevant_skills(db, agent_id: int, workspace: str, user_msg: str, top_k: int = 3) -> list[str]:
    """加载与当前对话相关的 Skill 内容
    
    策略：
    1. 加载智能体级 Skill（agent_id 匹配）
    2. 加载项目级 Skill（数据库 + .nix/skills/ 文件）
    3. 按关键词相关度排序
    4. 返回 top-k 个 Skill 的 content
    """
    from models.skill import Skill
    
    all_skills = []
    
    # 1. 智能体级（数据库）
    if agent_id:
        agent_skills = db.query(Skill).filter(
            Skill.agent_id == agent_id,
            Skill.scope == "agent",
            Skill.is_active == True
        ).all()
        for s in agent_skills:
            all_skills.append({
                "name": s.name,
                "content": s.content,
                "keywords": s.keywords or [],
                "score": 0
            })
    
    # 2. 项目级（数据库）
    project_skills_db = db.query(Skill).filter(
        Skill.scope == "project",
        Skill.is_active == True
    ).all()
    for s in project_skills_db:
        all_skills.append({
            "name": s.name,
            "content": s.content,
            "keywords": s.keywords or [],
            "score": 0
        })
    
    # 3. 项目级（.nix/skills/ 文件）
    if workspace:
        file_skills = load_nix_skill_files(workspace)
        for s in file_skills:
            # 避免与数据库重复（按 name 去重）
            if not any(existing["name"] == s["name"] for existing in all_skills):
                all_skills.append({
                    "name": s["name"],
                    "content": s["content"],
                    "keywords": s.get("keywords", []),
                    "score": 0
                })
    
    if not all_skills:
        return []
    
    # 4. 关键词相关度打分
    msg_lower = user_msg.lower()
    for skill in all_skills:
        score = 0
        for kw in skill["keywords"]:
            if kw.lower() in msg_lower:
                score += 2
        # 名称匹配也给分
        if skill["name"].lower() in msg_lower:
            score += 1
        skill["score"] = score
    
    # 5. 排序，取 top-k（score > 0 的优先，如果都是 0 则全部返回让调用方决定）
    scored_skills = [s for s in all_skills if s["score"] > 0]
    if scored_skills:
        scored_skills.sort(key=lambda x: x["score"], reverse=True)
        return [s["content"] for s in scored_skills[:top_k]]
    
    # 如果没有关键词命中但 skill 总数很少（<=3），全部返回
    if len(all_skills) <= top_k:
        return [s["content"] for s in all_skills]
    
    return []
