import socket
import time

from fastapi import Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session

from dependencies.auth import get_current_user
from models.database import get_db
from models.user import User
from models.db_connection import DbConnection
from schemas.db_connection import (
    DbConnectionCreate,
    DbConnectionUpdate,
    DbConnectionResponse,
    DbConnectionTestResponse,
)

router = APIRouter()


@router.get("", response_model=list[DbConnectionResponse])
def list_connections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rows = db.query(DbConnection).filter(DbConnection.user_id == current_user.id).order_by(DbConnection.id).all()
    return rows


@router.post("", response_model=DbConnectionResponse)
def create_connection(
    payload: DbConnectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conn = DbConnection(**payload.model_dump(), user_id=current_user.id)
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@router.get("/{conn_id}", response_model=DbConnectionResponse)
def get_connection(
    conn_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conn = db.query(DbConnection).filter(
        DbConnection.id == conn_id,
        DbConnection.user_id == current_user.id
    ).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return conn


@router.put("/{conn_id}", response_model=DbConnectionResponse)
def update_connection(
    conn_id: int,
    payload: DbConnectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conn = db.query(DbConnection).filter(
        DbConnection.id == conn_id,
        DbConnection.user_id == current_user.id
    ).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(conn, k, v)
    db.commit()
    db.refresh(conn)
    return conn


@router.delete("/{conn_id}")
def delete_connection(
    conn_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conn = db.query(DbConnection).filter(
        DbConnection.id == conn_id,
        DbConnection.user_id == current_user.id
    ).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    db.delete(conn)
    db.commit()
    return {"message": "Deleted"}


@router.post("/{conn_id}/test", response_model=DbConnectionTestResponse)
def test_connection(
    conn_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conn = db.query(DbConnection).filter(
        DbConnection.id == conn_id,
        DbConnection.user_id == current_user.id
    ).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    start = time.time()
    try:
        sock = socket.create_connection((conn.host, conn.port), timeout=5)
        sock.close()
        latency_ms = (time.time() - start) * 1000
        return DbConnectionTestResponse(
            success=True,
            message="Connection successful",
            latency_ms=round(latency_ms, 2)
        )
    except Exception as e:
        return DbConnectionTestResponse(
            success=False,
            message=str(e),
            latency_ms=None
        )
