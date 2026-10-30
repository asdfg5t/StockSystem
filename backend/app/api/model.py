from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.db_models import ModelConfig, ModelFile
from app.models.schemas import ResponseBase, ModelConfigUpdate
from app.utils.logger import get_logger

logger = get_logger("model_api")
router = APIRouter(prefix="/model", tags=["模型管理"])


@router.get("/configs")
def get_model_configs(
    model_type: str = Query(""),
    db: Session = Depends(get_db),
):
    query = db.query(ModelConfig)
    if model_type:
        query = query.filter(ModelConfig.model_type == model_type)
    configs = query.all()
    return ResponseBase(data=[{
        "id": c.id,
        "model_name": c.model_name,
        "model_type": c.model_type,
        "params": c.params,
        "description": c.description,
        "is_active": c.is_active,
        "created_at": str(c.created_at) if c.created_at else None,
    } for c in configs])


@router.put("/config/{config_id}")
def update_model_config(
    config_id: int, req: ModelConfigUpdate, db: Session = Depends(get_db)
):
    config = db.query(ModelConfig).filter(ModelConfig.id == config_id).first()
    if not config:
        return ResponseBase(code=404, message="模型配置不存在")
    if req.model_name is not None:
        config.model_name = req.model_name
    if req.params is not None:
        config.params = req.params
    if req.description is not None:
        config.description = req.description
    if req.is_active is not None:
        config.is_active = req.is_active
    db.commit()
    return ResponseBase(message="更新成功")


@router.get("/files")
def get_model_files(
    model_type: str = Query(""),
    ts_code: str = Query(""),
    predict_steps: int = Query(0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(ModelFile)
    if model_type:
        query = query.filter(ModelFile.model_type == model_type)
    if ts_code:
        query = query.filter(ModelFile.ts_code == ts_code)
    if predict_steps > 0:
        query = query.filter(ModelFile.predict_steps == predict_steps)

    total = query.count()
    items = query.order_by(ModelFile.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return ResponseBase(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [{
            "id": m.id,
            "train_task_id": m.train_task_id,
            "model_type": m.model_type,
            "ts_code": m.ts_code,
            "predict_steps": m.predict_steps,
            "file_path": m.file_path,
            "metrics": m.metrics,
            "is_best": m.is_best,
            "file_size": m.file_size,
            "created_at": str(m.created_at) if m.created_at else None,
        } for m in items],
    })


@router.delete("/file/{file_id}")
def delete_model_file(file_id: int, db: Session = Depends(get_db)):
    model_file = db.query(ModelFile).filter(ModelFile.id == file_id).first()
    if not model_file:
        return ResponseBase(code=404, message="模型文件不存在")
    import os
    if os.path.exists(model_file.file_path):
        os.remove(model_file.file_path)
    db.delete(model_file)
    db.commit()
    return ResponseBase(message="删除成功")
