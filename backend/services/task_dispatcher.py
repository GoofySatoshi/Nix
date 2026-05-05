import logging
import threading
import time
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

# 智能体类型 → 能处理的意图标签映射
AGENT_CAPABILITY_MAP = {
    "developer": ["file_operation", "code_analysis", "terminal_command", "project_task"],
    "analyst": ["code_analysis", "information_query"],
    "operator": ["terminal_command", "file_operation"],
    "assistant": ["general_chat", "information_query"],
    "tester": ["terminal_command", "code_analysis"],
    # 默认：所有类型的智能体都能处理 general_chat
}

# 调度器状态
class TaskDispatcher:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._running = False
        self._thread = None
        self._dispatch_interval = 10  # 秒
        self._task_progress: Dict[int, Dict] = {}  # task_id -> {progress, message}
        logger.info("TaskDispatcher 初始化完成")

    def start(self):
        """启动调度器"""
        logger.info("[TaskDispatcher.start] 入参: 无")
        if self._running:
            logger.info("[TaskDispatcher.start] 返回: 已在运行")
            return
        self._running = True
        self._thread = threading.Thread(target=self._dispatch_loop, daemon=True)
        self._thread.start()
        logger.info("TaskDispatcher 已启动")

    def stop(self):
        """停止调度器"""
        logger.info("[TaskDispatcher.stop] 入参: 无")
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("TaskDispatcher 已停止")

    def _dispatch_loop(self):
        """主调度循环"""
        logger.info("[TaskDispatcher._dispatch_loop] 调度循环已启动")
        while self._running:
            try:
                self._do_dispatch()
            except Exception as e:
                logger.error(f"调度循环异常: {e}")
            time.sleep(self._dispatch_interval)

    def _do_dispatch(self):
        """执行一轮调度"""
        logger.info("[TaskDispatcher._do_dispatch] 入参: 无")
        from models import get_db, Task, Agent

        db = next(get_db())
        try:
            # 查找待分配的任务（status=pending，无 agent_id）
            pending_tasks = db.query(Task).filter(
                Task.status == "pending",
            ).order_by(Task.priority.desc(), Task.created_at.asc()).limit(10).all()

            if not pending_tasks:
                return

            # 查找运行中的智能体
            running_agents = db.query(Agent).filter(
                Agent.status == "running"
            ).all()

            if not running_agents:
                return

            for task in pending_tasks:
                # 获取任务的意图标签
                intent_tag = getattr(task, 'intent_tag', None) or "general_chat"

                # 找到匹配的智能体
                best_agent = self._find_matching_agent(
                    intent_tag, running_agents, db
                )

                if best_agent:
                    # 分配任务
                    task.agent_id = best_agent.id
                    task.status = "in_progress"
                    task.updated_at = datetime.utcnow()

                    # 更新进度
                    self._task_progress[task.id] = {
                        "progress": 10,
                        "message": f"已分配给智能体 {best_agent.name}",
                    }

                    logger.info(
                        f"任务 #{task.id} '{task.name}' 已分配给智能体 "
                        f"'{best_agent.name}' (标签: {intent_tag})"
                    )

            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"调度失败: {e}")
        finally:
            db.close()

    def _find_matching_agent(self, intent_tag: str, agents, db) -> Optional[object]:
        """根据意图标签找到最匹配的智能体"""
        logger.info(f"[TaskDispatcher._find_matching_agent] 入参: intent_tag={intent_tag}, agents数={len(agents)}")
        from models import Task

        candidates = []
        for agent in agents:
            agent_type = (agent.type or "assistant").lower()
            capabilities = AGENT_CAPABILITY_MAP.get(agent_type, ["general_chat"])

            if intent_tag in capabilities or capabilities == ["general_chat"]:
                # 计算当前工作负载
                active_tasks = db.query(Task).filter(
                    Task.agent_id == agent.id,
                    Task.status.in_(["pending", "in_progress"])
                ).count()
                candidates.append((agent, active_tasks))

        if not candidates:
            # 没有完全匹配的，选负载最低的
            for agent in agents:
                active_tasks = db.query(Task).filter(
                    Task.agent_id == agent.id,
                    Task.status.in_(["pending", "in_progress"])
                ).count()
                candidates.append((agent, active_tasks))

        if candidates:
            # 选负载最低的
            candidates.sort(key=lambda x: x[1])
            result = candidates[0][0]
            logger.info(f"[TaskDispatcher._find_matching_agent] 返回: agent={result.name if hasattr(result, 'name') else result}")
            return result

        logger.info("[TaskDispatcher._find_matching_agent] 返回: None")
        return None

    def get_task_progress(self, task_id: int) -> Dict:
        """获取任务进度"""
        logger.info(f"[TaskDispatcher.get_task_progress] 入参: task_id={task_id}")
        result = self._task_progress.get(task_id, {"progress": 0, "message": "等待中"})
        logger.info(f"[TaskDispatcher.get_task_progress] 返回: progress={result.get('progress', 0)}")
        return result

    def update_task_progress(self, task_id: int, progress: int, message: str):
        """更新任务进度"""
        logger.info(f"[TaskDispatcher.update_task_progress] 入参: task_id={task_id}, progress={progress}, message={message[:50]}")
        self._task_progress[task_id] = {"progress": progress, "message": message}


# 全局调度器实例
dispatcher = TaskDispatcher()
