from sqlalchemy.orm import Session
from models import Task
from schemas.task import TaskCreate, TaskUpdate
from services.agent_manager import get_agent_instance
import traceback
import json
import logging

logger = logging.getLogger(__name__)

# 内存任务队列
task_queue = []

def _broadcast_task_update(task_id: int, status: str, extra: dict = None):
    """通过 WebSocket 广播任务状态更新"""
    logger.info(f"[TaskExecutor._broadcast_task_update] 入参: task_id={task_id}, status={status}, extra_keys={list(extra.keys()) if extra else None}")
    try:
        from main import manager
        import asyncio
        message = {"type": "task_update", "task_id": task_id, "status": status}
        if extra:
            message.update(extra)
        # 在后台线程中运行异步广播
        loop = asyncio.new_event_loop()
        loop.run_until_complete(manager.broadcast(message))
        loop.close()
    except Exception:
        pass  # WebSocket 广播失败不影响主流程

def create_task(db: Session, task: TaskCreate) -> Task:
    """创建任务"""
    logger.info(f"[TaskExecutor.create_task] 入参: name={task.name}, agent_id={task.agent_id}, priority={task.priority}")
    db_task = Task(
        name=task.name,
        description=task.description,
        agent_id=task.agent_id,
        status="pending",
        dependencies=task.dependencies or [],
        priority=task.priority or 0,
        mermaid_syntax=task.mermaid_syntax
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    
    # 将任务添加到队列
    task_queue.append(db_task.id)
    # 按优先级排序队列
    sort_task_queue(db)
    
    # 尝试执行任务
    execute_task(db, db_task.id)
    
    logger.info(f"[TaskExecutor.create_task] 返回: task_id={db_task.id}")
    return db_task

def get_task(db: Session, task_id: int) -> Task:
    """获取任务"""
    logger.info(f"[TaskExecutor.get_task] 入参: task_id={task_id}")
    result = db.query(Task).filter(Task.id == task_id).first()
    logger.info(f"[TaskExecutor.get_task] 返回: {'found' if result else 'None'}")
    return result

def get_tasks(db: Session) -> list[Task]:
    """获取所有任务"""
    logger.info("[TaskExecutor.get_tasks] 入参: 无")
    result = db.query(Task).all()
    logger.info(f"[TaskExecutor.get_tasks] 返回: {len(result)} 个任务")
    return result

def update_task(db: Session, task_id: int, task: TaskUpdate) -> Task:
    """更新任务"""
    logger.info(f"[TaskExecutor.update_task] 入参: task_id={task_id}, name={task.name}, status={task.status}")
    db_task = get_task(db, task_id)
    if not db_task:
        return None
    
    if task.name is not None:
        db_task.name = task.name
    if task.description is not None:
        db_task.description = task.description
    if task.status is not None:
        db_task.status = task.status
    if task.dependencies is not None:
        db_task.dependencies = task.dependencies
    if task.priority is not None:
        db_task.priority = task.priority
    
    db.commit()
    db.refresh(db_task)
    
    # 重新排序任务队列
    sort_task_queue(db)
    # 尝试执行任务
    execute_task(db, db_task.id)
    
    logger.info(f"[TaskExecutor.update_task] 返回: task_id={db_task.id}, status={db_task.status}")
    return db_task

def delete_task(db: Session, task_id: int) -> bool:
    """删除任务"""
    logger.info(f"[TaskExecutor.delete_task] 入参: task_id={task_id}")
    db_task = get_task(db, task_id)
    if not db_task:
        return False
    
    # 从队列中移除
    if task_id in task_queue:
        task_queue.remove(task_id)
    
    db.delete(db_task)
    db.commit()
    logger.info(f"[TaskExecutor.delete_task] 返回: True")
    return True

def sort_task_queue(db: Session):
    """按优先级和依赖关系排序任务队列"""
    logger.info(f"[TaskExecutor.sort_task_queue] 入参: queue_size={len(task_queue)}")
    # 首先按优先级排序
    task_queue.sort(key=lambda task_id: get_task(db, task_id).priority if get_task(db, task_id) else 0, reverse=True)
    
    # 然后确保依赖任务在前面
    sorted_queue = []
    processed = set()
    
    def process_task(task_id):
        if task_id in processed:
            return
        
        task = get_task(db, task_id)
        if not task:
            return
        
        # 先处理依赖任务
        if task.dependencies:
            for dep_id in task.dependencies:
                process_task(dep_id)
        
        if task_id not in sorted_queue:
            sorted_queue.append(task_id)
        processed.add(task_id)
    
    for task_id in task_queue:
        process_task(task_id)
    
    # 更新队列
    task_queue.clear()
    task_queue.extend(sorted_queue)
    logger.info(f"[TaskExecutor.sort_task_queue] 返回: 排序后 queue_size={len(task_queue)}")

def execute_task(db: Session, task_id: int):
    """执行任务 — 调用真实智能体实例"""
    logger.info(f"[TaskExecutor.execute_task] 入参: task_id={task_id}")
    db_task = get_task(db, task_id)
    if not db_task:
        return
    
    # 检查任务是否已完成
    if db_task.status in ("completed", "failed"):
        return
    
    # 检查依赖任务是否完成
    if db_task.dependencies:
        for dep_id in db_task.dependencies:
            dep_task = get_task(db, dep_id)
            if not dep_task or dep_task.status != "completed":
                return
    
    # 检查是否指定了智能体
    if not db_task.agent_id:
        db_task.status = "failed"
        db_task.execution_log = "未指定智能体"
        db.commit()
        _broadcast_task_update(task_id, "failed", {"execution_log": "未指定智能体"})
        return
    
    # 获取智能体实例
    agent_instance = get_agent_instance(db_task.agent_id)
    if not agent_instance:
        db_task.status = "failed"
        db_task.execution_log = f"智能体 {db_task.agent_id} 未启动或不存在"
        db.commit()
        _broadcast_task_update(task_id, "failed", {"execution_log": db_task.execution_log})
        return
    
    # 真正执行任务
    try:
        db_task.status = "running"
        db_task.execution_log = "任务开始执行..."
        db.commit()
        _broadcast_task_update(task_id, "running")
        
        # 构建任务数据传给智能体
        task_data = {
            "id": db_task.id,
            "name": db_task.name,
            "description": db_task.description,
            "priority": db_task.priority
        }
        
        # 调用智能体的 process 方法
        result = agent_instance.process(task_data)
        
        # 存储执行结果
        db_task.result = result
        db_task.status = "completed"
        db_task.execution_log = f"任务执行完成\n结果: {json.dumps(result, ensure_ascii=False)}"
        db.commit()
        logger.info(f"[TaskExecutor.execute_task] task_id={task_id} 执行完成")
        _broadcast_task_update(task_id, "completed", {"result": result})
        
        # 执行完当前任务后，检查并执行队列中的其他任务
        for tid in list(task_queue):
            execute_task(db, tid)
    except Exception as e:
        logger.error(f"[TaskExecutor.execute_task] task_id={task_id} 执行失败: {e}", exc_info=True)
        db_task.status = "failed"
        db_task.execution_log = f"执行失败: {str(e)}\n{traceback.format_exc()}"
        db.commit()
        _broadcast_task_update(task_id, "failed", {"execution_log": str(e)})
