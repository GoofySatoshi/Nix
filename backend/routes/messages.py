from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from models import Message, get_db, User, Task
from models.workflow import WorkflowStep
from schemas.message import MessageCreate, MessageBatchCreate, MessageResponse
from dependencies.auth import get_current_user
from services.agent_manager import agent_instances

router = APIRouter()


@router.get("", response_model=list[MessageResponse])
def get_messages(
    agent_id: Optional[int] = Query(None),
    task_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """按智能体或任务获取对话历史（默认最近50条）"""
    query = db.query(Message).filter(Message.user_id == current_user.id)

    if agent_id is not None:
        query = query.filter(Message.agent_id == agent_id)
    if task_id is not None:
        query = query.filter(Message.task_id == task_id)

    messages = query.order_by(Message.id.asc()).offset(offset).limit(limit).all()
    return messages


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def create_message(
    message: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """保存一条消息"""
    db_message = Message(
        agent_id=message.agent_id,
        user_id=current_user.id,
        role=message.role,
        content=message.content,
        tool_calls=message.tool_calls,
        intent=message.intent,
        task_id=message.task_id,
        model_name=message.model_name,
        config_name=message.config_name,
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message


@router.post("/batch", response_model=list[MessageResponse], status_code=status.HTTP_201_CREATED)
def create_messages_batch(
    batch: MessageBatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量保存消息（常用于一次性保存用户消息+AI回复）"""
    db_messages = []
    for msg in batch.messages:
        db_message = Message(
            agent_id=msg.agent_id,
            user_id=current_user.id,
            role=msg.role,
            content=msg.content,
            tool_calls=msg.tool_calls,
            intent=msg.intent,
            task_id=msg.task_id,
            model_name=msg.model_name,
            config_name=msg.config_name,
        )
        db.add(db_message)
        db_messages.append(db_message)

    db.commit()
    for db_message in db_messages:
        db.refresh(db_message)
    return db_messages


@router.delete("")
def delete_messages(
    agent_id: Optional[int] = Query(None),
    task_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """清除某个智能体或任务的对话历史"""
    query = db.query(Message).filter(Message.user_id == current_user.id)

    if agent_id is not None:
        query = query.filter(Message.agent_id == agent_id)
    elif task_id is not None:
        query = query.filter(Message.task_id == task_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必须提供 agent_id 或 task_id 参数"
        )

    deleted_count = query.delete(synchronize_session=False)

    # 级联清除关联的任务和工作流步骤
    if agent_id is not None:
        tasks = db.query(Task).filter(Task.agent_id == agent_id).all()
        for task in tasks:
            db.query(WorkflowStep).filter(WorkflowStep.task_id == task.id).delete(synchronize_session=False)
        db.query(Task).filter(Task.agent_id == agent_id).delete(synchronize_session=False)

        # 重置智能体实例缓存（清除内部状态）
        if agent_id in agent_instances:
            del agent_instances[agent_id]

    db.commit()
    return {"message": "对话历史已清除", "deleted_count": deleted_count}
