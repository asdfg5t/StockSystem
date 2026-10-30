from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.db_models import SystemConfig, SystemLog
from app.models.schemas import ResponseBase, SystemConfigUpdate

router = APIRouter(prefix="/system", tags=["系统配置"])


@router.get("/configs")
def get_system_configs(db: Session = Depends(get_db)):
    configs = db.query(SystemConfig).all()
    return ResponseBase(data=[{
        "id": c.id,
        "config_key": c.config_key,
        "config_value": c.config_value,
        "config_type": c.config_type,
        "description": c.description,
    } for c in configs])


@router.put("/config/{config_key}")
def update_system_config(
    config_key: str, req: SystemConfigUpdate, db: Session = Depends(get_db)
):
    config = db.query(SystemConfig).filter(
        SystemConfig.config_key == config_key
    ).first()
    if not config:
        return ResponseBase(code=404, message="配置不存在")
    config.config_value = req.config_value
    db.commit()
    return ResponseBase(message="更新成功")


@router.get("/logs")
def get_system_logs(
    module: str = Query(""),
    level: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(SystemLog)
    if module:
        query = query.filter(SystemLog.module == module)
    if level:
        query = query.filter(SystemLog.level == level)

    total = query.count()
    items = query.order_by(SystemLog.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return ResponseBase(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [{
            "id": l.id,
            "module": l.module,
            "level": l.level,
            "message": l.message,
            "detail": l.detail,
            "created_at": str(l.created_at) if l.created_at else None,
        } for l in items],
    })


@router.get("/log_files")
def get_log_files():
    import os
    from app.config import LOG_DIR
    files = []
    if LOG_DIR.exists():
        for f in sorted(LOG_DIR.iterdir(), reverse=True):
            if f.is_file() and f.suffix in (".log", ".zip"):
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "modified": str(f.stat().st_mtime),
                })
    return ResponseBase(data=files[:50])


@router.get("/log_content/{filename}")
def get_log_content(
    filename: str,
    lines: int = Query(200, ge=1, le=1000),
):
    from app.config import LOG_DIR
    file_path = LOG_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        return ResponseBase(code=404, message="日志文件不存在")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        content = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return ResponseBase(data={
            "filename": filename,
            "total_lines": len(all_lines),
            "content": "".join(content),
        })
    except Exception as e:
        return ResponseBase(code=500, message=str(e))
