from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from models import Task, get_db, User
from schemas.task import TaskCreate, TaskUpdate, TaskResponse
from services.task_executor import create_task, get_task, get_tasks, update_task, delete_task, execute_task
from dependencies.auth import get_current_user

router = APIRouter()

@router.get("", response_model=list[TaskResponse])
def get_task_list(
    status_filter: Optional[str] = Query(None, alias="status"),
    agent_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Task)
    if status_filter:
        query = query.filter(Task.status == status_filter)
    if agent_id:
        query = query.filter(Task.agent_id == agent_id)
    if search:
        query = query.filter(Task.name.ilike(f"%{search}%"))
    tasks = query.order_by(desc(Task.priority), desc(Task.created_at)).all()
    return tasks

@router.post("", response_model=TaskResponse)
def create_task_endpoint(task: TaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_task = create_task(db, task)
    return db_task

@router.get("/{task_id}", response_model=TaskResponse)
def get_task_endpoint(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_task = get_task(db, task_id)
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    return db_task

@router.put("/{task_id}", response_model=TaskResponse)
def update_task_endpoint(task_id: int, task: TaskUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_task = update_task(db, task_id, task)
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    return db_task

@router.delete("/{task_id}")
def delete_task_endpoint(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    success = delete_task(db, task_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    return {"message": "Task deleted successfully"}

@router.post("/{task_id}/execute")
def execute_task_endpoint(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_task = get_task(db, task_id)
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    if db_task.status in ("completed", "running"):
        return {"message": f"Task is already {db_task.status}", "task_id": task_id}
    execute_task(db, task_id)
    db.refresh(db_task)
    return {"message": "Task execution triggered", "task_id": task_id, "status": db_task.status}