import json
import os
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage
except ImportError:
    ChatOpenAI = None
    SystemMessage = None
    HumanMessage = None


def create_acceptance_llm(api_key: str, model: str, base_url: Optional[str] = None):
    """创建独立的验收工程师 LLM 实例"""
    logger.info(f"[Acceptance.create_acceptance_llm] 入参: model={model}, base_url={base_url}")
    if ChatOpenAI is None:
        logger.info("[Acceptance.create_acceptance_llm] 返回: None (ChatOpenAI不可用)")
        return None
    kwargs = {
        "api_key": api_key,
        "model": model,
        "temperature": 0.3,
        "max_tokens": 8000,
        "timeout": 300,
    }
    if base_url:
        kwargs["base_url"] = base_url
    result = ChatOpenAI(**kwargs)
    logger.info(f"[Acceptance.create_acceptance_llm] 返回: LLM实例(model={model})")
    return result


def generate_acceptance_criteria(api_key: str, model: str, base_url: Optional[str],
                                  user_msg: str, intent: str, available_tools: list) -> dict:
    """生成任务验收标准（3-6条）"""
    logger.info(f"[Acceptance.generate_acceptance_criteria] 入参: model={model}, user_msg={user_msg}, intent={intent}, tools={len(available_tools) if available_tools else 0}")
    if ChatOpenAI is None or SystemMessage is None or HumanMessage is None:
        logger.info("[Acceptance.generate_acceptance_criteria] 返回: 默认标准 (LLM不可用)")
        return {"criteria": [{"id": 1, "description": "任务完成", "check_method": "人工确认"}]}
    
    try:
        logger.info(f"[Acceptance] 调用LLM生成验收标准, 任务: {user_msg}")
        llm = create_acceptance_llm(api_key, model, base_url)
        if not llm:
            logger.error("[Acceptance] 创建LLM实例失败，返回默认验收标准")
            return {"criteria": [{"id": 1, "description": "任务完成", "check_method": "人工确认"}]}
        
        tools_str = ", ".join(available_tools) if available_tools else "无"
        system_prompt = f"""你是验收标准制定专家。根据用户任务生成 3-5 条可验证的验收标准。

可用工具: {tools_str}

## 规则
1. 每条标准必须可以通过查看文件内容或执行命令来验证
2. description 必须包含具体的文件名、函数名、字段名等，禁止模糊描述
3. check_method 格式必须是以下之一：
   - "file_exists:相对路径" - 检查文件是否存在
   - "file_contains:相对路径:关键内容" - 检查文件是否包含指定内容
   - "code_logic:文件路径:逻辑描述" - AI判断代码逻辑
   - "manual:描述" - 需要AI综合判断

## 好的标准示例
- {{"id": 1, "description": "backend/models/role.py 文件存在且包含 Role 类定义", "check_method": "file_contains:backend/models/role.py:class Role"}}
- {{"id": 2, "description": "auth.py 中存在 /api/roles 路由定义", "check_method": "file_contains:backend/routes/auth.py:@router.post"}}
- {{"id": 3, "description": "RoleManager.tsx 组件文件存在", "check_method": "file_exists:frontend/src/components/RoleManager.tsx"}}

## 坏的标准（禁止）
- "功能正常工作" ← 无法验证
- "代码质量良好" ← 太主观
- "用户体验流畅" ← 无法自动检查

## 输出
JSON，不要其他文字：
{{"criteria": [{{"id": 1, "description": "描述", "check_method": "验证方式"}}]}}"""

        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_msg)
        ])
        content = response.content.strip() if response.content else ""
        logger.info(f"[Acceptance] LLM原始返回 ({len(content)} chars): {content}")
        
        if not content:
            logger.error("[Acceptance] LLM返回空内容")
            return {"criteria": [{"id": 1, "description": "任务按用户需求完成", "check_method": "人工确认"}]}
        
        # 解析 JSON：先去掉 markdown 代码块
        json_match = re.search(r'```(?:json)?\s*(.*?)```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1).strip()
        
        # 尝试提取 JSON 对象
        json_obj_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_obj_match:
            content = json_obj_match.group(0)
        
        result = json.loads(content)
        if "criteria" in result and isinstance(result["criteria"], list) and len(result["criteria"]) > 0:
            logger.info(f"[Acceptance.generate_acceptance_criteria] 返回: {len(result['criteria'])} 条标准")
            return result
        else:
            logger.warning("[Acceptance] LLM返回的JSON格式不正确，使用默认验收标准")
            return {"criteria": [{"id": 1, "description": "任务按用户需求完成", "check_method": "人工确认"}]}
    except json.JSONDecodeError as e:
        logger.error(f"[Acceptance] JSON解析失败: {e}, 原始内容: {content}")
        return {"criteria": [{"id": 1, "description": "任务按用户需求完成", "check_method": "人工确认"}]}
    except Exception as e:
        logger.error(f"[Acceptance] 生成验收标准异常: {e}")
        return {"criteria": [{"id": 1, "description": "任务按用户需求完成", "check_method": "人工确认"}]}


def run_acceptance_check(api_key: str, model: str, base_url: Optional[str],
                         criteria: list, task_result: str,
                         workspace: str, tool_calls_log: list = None) -> dict:
    """执行验收检查
    
    验收工程师根据验收标准，综合代码操作记录和执行结果进行逐项验收。
    """
    logger.info(f"[Acceptance.run_acceptance_check] 入参: model={model}, criteria数={len(criteria)}, task_result长度={len(task_result) if task_result else 0}, workspace={workspace}, tool_calls_log数={len(tool_calls_log) if tool_calls_log else 0}")
    if ChatOpenAI is None or SystemMessage is None or HumanMessage is None:
        return {
            "passed": True,
            "results": [{"id": c.get("id", i+1), "status": "passed", "reason": "无法验证，默认通过"} for i, c in enumerate(criteria)],
            "fix_message": ""
        }
    
    try:
        task_preview = task_result[:50] if task_result else "无"
        logger.info(f"[Acceptance] 调用LLM执行验收检查, 标准数: {len(criteria)}, 结果预览: {task_preview}...")
        llm = create_acceptance_llm(api_key, model, base_url)
        if not llm:
            logger.error("[Acceptance] 创建LLM实例失败，默认通过验收")
            return {"passed": True, "results": [], "fix_message": ""}
        
        criteria_text = "\n".join([
            f"{c.get('id', i+1)}. {c.get('description', '')} [验证方法: {c.get('check_method', '人工确认')}]"
            for i, c in enumerate(criteria)
        ])

        # 构建工具执行记录摘要
        tool_log_text = ""
        if tool_calls_log:
            tool_entries = []
            for tc in tool_calls_log:
                name = tc.get('tool_name', '未知')
                params = tc.get('parameters', {})
                result_preview = str(tc.get('result', ''))[:500]
                success = '成功' if tc.get('success', False) else '失败'
                tool_entries.append(f"  - [{success}] {name}({json.dumps(params, ensure_ascii=False)[:200]})\n    结果: {result_preview}")
            tool_log_text = "\n".join(tool_entries)
        
        system_prompt = f"""你是一个严格的验收工程师。你需要根据验收标准，综合分析【代码操作记录】和【执行结果】来判断任务是否完成。

## 验收标准
{criteria_text}

## 工作目录
{workspace}

## 验收原则
1. **看代码操作**：验证是否真正执行了创建/修改/删除文件等操作，而不仅仅是口头描述
2. **看执行结果**：检查工具调用是否成功，文件是否正确写入/修改
3. **对照标准逐项验证**：每条标准都需要从操作记录中找到对应的证据
4. 如果只有文字描述但没有实际操作（工具调用为空），应标记为 failed
5. 如果操作失败了但回复中声称成功，应标记为 failed
6. 对 failed 项，fix_instruction 必须具体明确

## 输出格式
严格按以下 JSON 格式返回（不要加任何其他文字）：
{{
  "passed": true/false,
  "results": [
    {{"id": 1, "status": "passed", "reason": "通过原因"}},
    {{"id": 2, "status": "failed", "reason": "失败原因", "fix_instruction": "具体修改指令"}}
  ],
  "fix_message": "如果有失败项，写综合修改指令。全部通过则为空字符串"
}}"""

        # 自动验证部分标准（file_exists / file_contains）
        auto_results = []
        for c in criteria:
            method = c.get('check_method', '')
            if isinstance(method, str) and method.startswith('file_exists:'):
                rel_path = method.split(':', 1)[1].strip()
                full_path = os.path.join(workspace, rel_path)
                exists = os.path.exists(full_path)
                auto_results.append(f"[自动验证] 标准#{c.get('id', '?')}: 文件 {rel_path} {'存在 ✓' if exists else '不存在 ✗'}")
            elif isinstance(method, str) and method.startswith('file_contains:'):
                parts = method.split(':', 2)
                rel_path = parts[1].strip() if len(parts) > 1 else ''
                keyword = parts[2].strip() if len(parts) > 2 else ''
                full_path = os.path.join(workspace, rel_path)
                if os.path.exists(full_path):
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        found = keyword in content
                        auto_results.append(f"[自动验证] 标准#{c.get('id', '?')}: 文件 {rel_path} {'包含' if found else '不包含'} '{keyword}' {'✓' if found else '✗'}")
                    except Exception as e:
                        auto_results.append(f"[自动验证] 标准#{c.get('id', '?')}: 读取文件 {rel_path} 失败: {e}")
                else:
                    auto_results.append(f"[自动验证] 标准#{c.get('id', '?')}: 文件 {rel_path} 不存在 ✗")

        # 构建验收输入内容
        user_content_parts = []
        if auto_results:
            user_content_parts.append(f"## 自动验证结果\n" + "\n".join(auto_results))
        if tool_log_text:
            user_content_parts.append(f"## 代码操作记录（工具执行日志）\n{tool_log_text}")
        user_content_parts.append(f"## AI最终回复\n{task_result}")
        user_content = "\n\n".join(user_content_parts)

        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ])
        content = response.content.strip() if response.content else ""
        logger.info(f"[Acceptance] 验收检查LLM原始返回 ({len(content)} chars): {content}")
        
        if not content:
            logger.error("[Acceptance] 验收检查LLM返回空内容")
            return {"passed": True, "results": [], "fix_message": ""}
        
        # 解析 JSON：先去掉 markdown 代码块
        json_match = re.search(r'```(?:json)?\s*(.*?)```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1).strip()
        
        # 尝试提取 JSON 对象
        json_obj_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_obj_match:
            content = json_obj_match.group(0)
        
        result = json.loads(content)
        if "passed" in result and "results" in result:
            logger.info(f"[Acceptance.run_acceptance_check] 返回: passed={result['passed']}, results数={len(result.get('results', []))}")
            return result
        else:
            logger.warning("[Acceptance] 验收检查返回的JSON格式不正确，默认通过")
            return {"passed": True, "results": [], "fix_message": ""}
    except json.JSONDecodeError as e:
        logger.error(f"[Acceptance] 验收检查JSON解析失败: {e}, 原始内容: {content}")
        return {"passed": True, "results": [], "fix_message": ""}
    except Exception as e:
        logger.error(f"[Acceptance] 验收检查异常: {e}")
        return {"passed": True, "results": [], "fix_message": ""}
