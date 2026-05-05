from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from models.database import get_db
from models.system_settings import SystemSettings
from schemas.system_settings import SystemSettingsResponse, SystemSettingsUpdate
from dependencies.auth import get_current_user

router = APIRouter()

@router.get("", response_model=SystemSettingsResponse)
def get_system_settings(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """获取系统设置（单例，只有一条记录）"""
    settings = db.query(SystemSettings).first()
    if not settings:
        settings = SystemSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings

@router.put("", response_model=SystemSettingsResponse)
def update_system_settings(data: SystemSettingsUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """更新系统设置"""
    settings = db.query(SystemSettings).first()
    if not settings:
        settings = SystemSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings, key, value)
    
    db.commit()
    db.refresh(settings)
    return settings
