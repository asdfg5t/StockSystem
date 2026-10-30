import threading
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.models.db_models import CollectTask, CollectLog
from app.models.schemas import ResponseBase, PageResponse, CollectTaskCreate
from app.services.data_collector import (
    collect_stock_basic, collect_daily_data, get_collect_progress
)
from app.utils.logger import get_logger

logger = get_logger("collect_api")
router = APIRouter(prefix="/collect", tags=["数据采集"])


@router.post("/create")
def create_collect_task(req: CollectTaskCreate, db: Session = Depends(get_db)):
    task = CollectTask(
        task_name=req.task_name,
        task_type=req.task_type,
        ts_code=req.ts_code,
        start_date=req.start_date,
        end_date=req.end_date,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return ResponseBase(data={"id": task.id, "status": task.status})


@router.post("/start/{task_id}")
def start_collect_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(CollectTask).filter(CollectTask.id == task_id).first()
    if not task:
        return ResponseBase(code=404, message="任务不存在")
    if task.status == "running":
        return ResponseBase(code=400, message="任务正在运行中")

    def _run():
        session = SessionLocal()
        try:
            if task.task_type == "stock_basic":
                collect_stock_basic(session, task_id)
            elif task.task_type == "daily":
                collect_daily_data(session, task_id)
            else:
                logger.error(f"未知的采集类型: {task.task_type}")
        finally:
            session.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    logger.info(f"采集任务 {task_id} 已启动")
    return ResponseBase(message="采集任务已启动")


@router.get("/progress/{task_id}")
def get_task_progress(task_id: int, db: Session = Depends(get_db)):
    progress = get_collect_progress(db, task_id)
    if not progress:
        return ResponseBase(code=404, message="任务不存在")
    return ResponseBase(data=progress)


@router.get("/tasks")
def get_collect_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(""),
    db: Session = Depends(get_db),
):
    query = db.query(CollectTask)
    if status:
        query = query.filter(CollectTask.status == status)
    total = query.count()
    items = query.order_by(CollectTask.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return PageResponse(
        data=[_task_to_dict(t) for t in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/logs/{task_id}")
def get_collect_logs(
    task_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(CollectLog).filter(CollectLog.task_id == task_id)
    total = query.count()
    items = query.order_by(CollectLog.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return PageResponse(
        data=[_log_to_dict(l) for l in items],
        total=total, page=page, page_size=page_size,
    )


@router.delete("/task/{task_id}")
def delete_collect_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(CollectTask).filter(CollectTask.id == task_id).first()
    if not task:
        return ResponseBase(code=404, message="任务不存在")
    if task.status == "running":
        return ResponseBase(code=400, message="任务运行中，无法删除")
    db.query(CollectLog).filter(CollectLog.task_id == task_id).delete()
    db.delete(task)
    db.commit()
    return ResponseBase(message="删除成功")


def _task_to_dict(t):
    return {
        "id": t.id, "task_name": t.task_name, "task_type": t.task_type,
        "ts_code": t.ts_code, "start_date": t.start_date,
        "end_date": t.end_date, "status": t.status,
        "total_count": t.total_count, "success_count": t.success_count,
        "fail_count": t.fail_count,
        "progress": float(t.progress) if t.progress else 0,
        "error_msg": t.error_msg,
        "started_at": str(t.started_at) if t.started_at else None,
        "finished_at": str(t.finished_at) if t.finished_at else None,
        "created_at": str(t.created_at) if t.created_at else None,
    }


def _log_to_dict(l):
    return {
        "id": l.id, "task_id": l.task_id, "ts_code": l.ts_code,
        "status": l.status, "message": l.message,
        "retry_count": l.retry_count,
        "created_at": str(l.created_at) if l.created_at else None,
    }
