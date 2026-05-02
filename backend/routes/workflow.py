from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models.database import get_db
from models.workflow import WorkflowStep
from models.user import User
from schemas.workflow import WorkflowStepCreate, WorkflowStepUpdate, WorkflowStepResponse
from typing import List
from dependencies.auth import get_current_user

router = APIRouter()

@router.post("/", response_model=WorkflowStepResponse)
def create_workflow_step(step: WorkflowStepCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_step = WorkflowStep(**step.model_dump())
    db.add(db_step)
    db.commit()
    db.refresh(db_step)
    return db_step

@router.get("/task/{task_id}", response_model=List[WorkflowStepResponse])
def get_workflow_steps(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    steps = db.query(WorkflowStep).filter(WorkflowStep.task_id == task_id).order_by(WorkflowStep.order).all()
    return steps

@router.get("/{step_id}", response_model=WorkflowStepResponse)
def get_workflow_step(step_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    step = db.query(WorkflowStep).filter(WorkflowStep.id == step_id).first()
    if not step:
        raise HTTPException(status_code=404, detail="Workflow step not found")
    return step

@router.put("/{step_id}", response_model=WorkflowStepResponse)
def update_workflow_step(step_id: int, step: WorkflowStepUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_step = db.query(WorkflowStep).filter(WorkflowStep.id == step_id).first()
    if not db_step:
        raise HTTPException(status_code=404, detail="Workflow step not found")
    for key, value in step.model_dump(exclude_unset=True).items():
        setattr(db_step, key, value)
    db.commit()
    db.refresh(db_step)
    return db_step

@router.delete("/{step_id}")
def delete_workflow_step(step_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_step = db.query(WorkflowStep).filter(WorkflowStep.id == step_id).first()
    if not db_step:
        raise HTTPException(status_code=404, detail="Workflow step not found")
    db.delete(db_step)
    db.commit()
    return {"message": "Workflow step deleted successfully"}
