import json
import threading
from pathlib import Path
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.models.db_models import TrainTask, TrainMetric
from app.models.schemas import ResponseBase, PageResponse, TrainTaskCreate
from app.services.trainer import run_training
from app.utils.logger import get_logger

logger = get_logger("train_api")
router = APIRouter(prefix="/train", tags=["模型训练"])

# smart_results 落盘目录：run_smart_train.py 训练后的指标快照
SMART_RESULTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "smart_results"
SMART_MODELS = ["BiLSTM", "Transformer", "TFT"]
SMART_STEPS = [1, 3, 5]


@router.post("/create")
def create_train_task(req: TrainTaskCreate, db: Session = Depends(get_db)):
    task = TrainTask(
        task_name=req.task_name,
        model_type=req.model_type,
        ts_code=req.ts_code,
        predict_steps=req.predict_steps,
        lookback_window=req.lookback_window,
        epochs=req.epochs,
        batch_size=req.batch_size,
        learning_rate=req.learning_rate,
        train_start_date=req.train_start_date,
        train_end_date=req.train_end_date,
        val_ratio=req.val_ratio,
        test_ratio=req.test_ratio,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return ResponseBase(data={"id": task.id, "status": task.status})


@router.post("/start/{task_id}")
def start_train_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(TrainTask).filter(TrainTask.id == task_id).first()
    if not task:
        return ResponseBase(code=404, message="任务不存在")
    if task.status == "running":
        return ResponseBase(code=400, message="任务正在运行中")

    def _run():
        session = SessionLocal()
        try:
            run_training(session, task_id)
        finally:
            session.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    logger.info(f"训练任务 {task_id} 已启动")
    return ResponseBase(message="训练任务已启动")


@router.get("/tasks")
def get_train_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    model_type: str = Query(""),
    status: str = Query(""),
    db: Session = Depends(get_db),
):
    query = db.query(TrainTask)
    if model_type:
        query = query.filter(TrainTask.model_type == model_type)
    if status:
        query = query.filter(TrainTask.status == status)
    total = query.count()
    items = query.order_by(TrainTask.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return PageResponse(
        data=[_task_to_dict(t) for t in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/task/{task_id}")
def get_train_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(TrainTask).filter(TrainTask.id == task_id).first()
    if not task:
        return ResponseBase(code=404, message="任务不存在")
    return ResponseBase(data=_task_to_dict(task))


@router.get("/metrics/{task_id}")
def get_train_metrics(task_id: int, db: Session = Depends(get_db)):
    metrics = db.query(TrainMetric).filter(
        TrainMetric.task_id == task_id,
    ).order_by(TrainMetric.epoch.asc()).all()
    return ResponseBase(data=[{
        "epoch": m.epoch,
        "train_loss": float(m.train_loss) if m.train_loss else None,
        "val_loss": float(m.val_loss) if m.val_loss else None,
        "train_mae": float(m.train_mae) if m.train_mae else None,
        "val_mae": float(m.val_mae) if m.val_mae else None,
        "train_rmse": float(m.train_rmse) if m.train_rmse else None,
        "val_rmse": float(m.val_rmse) if m.val_rmse else None,
        "learning_rate": float(m.learning_rate) if m.learning_rate else None,
    } for m in metrics])


@router.get("/compare_metrics")
def compare_train_metrics(
    ts_code: str = Query("", description="留空则取每个模型最近一次训练"),
    predict_steps: int = Query(1),
    db: Session = Depends(get_db),
):
    """三模型训练曲线对比

    - 传入 ts_code：按指定股票 + 步长，对比 BiLSTM/Transformer/TFT。
    - 不传 ts_code：忽略股票，按 predict_steps 取每个模型类型最近一次完成的训练任务。
    """
    result = {}
    for mt in ["BiLSTM", "Transformer", "TFT"]:
        q = db.query(TrainTask).filter(
            TrainTask.model_type == mt,
            TrainTask.predict_steps == predict_steps,
            TrainTask.status == "completed",
        )
        if ts_code:
            q = q.filter(TrainTask.ts_code == ts_code)
        task = q.order_by(TrainTask.created_at.desc()).first()
        if task:
            metrics = db.query(TrainMetric).filter(
                TrainMetric.task_id == task.id,
            ).order_by(TrainMetric.epoch.asc()).all()
            last = metrics[-1] if metrics else None
            result[mt] = {
                "task_id": task.id,
                "task_name": task.task_name,
                "ts_code": task.ts_code,
                "predict_steps": task.predict_steps,
                "epochs_run": task.current_epoch or 0,
                "best_val_loss": float(task.best_val_loss) if task.best_val_loss else None,
                "final_val_mae": float(last.val_mae) if last and last.val_mae else None,
                "final_val_rmse": float(last.val_rmse) if last and last.val_rmse else None,
                "finished_at": str(task.finished_at) if task.finished_at else None,
                "metrics": [{
                    "epoch": m.epoch,
                    "train_loss": float(m.train_loss) if m.train_loss else None,
                    "val_loss": float(m.val_loss) if m.val_loss else None,
                    "train_mae": float(m.train_mae) if m.train_mae else None,
                    "val_mae": float(m.val_mae) if m.val_mae else None,
                    "train_rmse": float(m.train_rmse) if m.train_rmse else None,
                    "val_rmse": float(m.val_rmse) if m.val_rmse else None,
                } for m in metrics],
            }
    return ResponseBase(data=result)


@router.get("/smart_results")
def get_smart_results():
    """读取 smart_results/ 下 9 个 JSON（3 模型 × 3 步长）的训练快照。

    返回结构：
    {
      "items": [{
        "model_type": "BiLSTM", "predict_steps": 1,
        "epochs_trained": 100, "best_val_loss": ...,
        "test_evaluation": {... mae/rmse/mape/r2/accuracy_1pct ...},
        "epoch_metrics": [{epoch, train_loss, val_loss, ...}, ...]
      }, ...],
      "missing": ["TFT_step5.json", ...]   # 找不到的文件
    }
    """
    items = []
    missing = []
    for mt in SMART_MODELS:
        for step in SMART_STEPS:
            fname = f"{mt}_step{step}.json"
            fp = SMART_RESULTS_DIR / fname
            if not fp.exists():
                missing.append(fname)
                continue
            try:
                with open(fp, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                logger.warning(f"读取 {fname} 失败: {e}")
                missing.append(fname)
                continue
            items.append({
                "model_type": data.get("model_type", mt),
                "predict_steps": data.get("predict_steps", step),
                "num_stocks": data.get("num_stocks"),
                "epochs_trained": data.get("epochs_trained"),
                "best_val_loss": data.get("best_val_loss"),
                "param_count": data.get("param_count"),
                "test_evaluation": data.get("test_evaluation", {}),
                "epoch_metrics": data.get("epoch_metrics", []),
            })
    return ResponseBase(data={"items": items, "missing": missing})


@router.delete("/task/{task_id}")
def delete_train_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(TrainTask).filter(TrainTask.id == task_id).first()
    if not task:
        return ResponseBase(code=404, message="任务不存在")
    if task.status == "running":
        return ResponseBase(code=400, message="任务运行中，无法删除")
    db.query(TrainMetric).filter(TrainMetric.task_id == task_id).delete()
    db.delete(task)
    db.commit()
    return ResponseBase(message="删除成功")


def _task_to_dict(t):
    return {
        "id": t.id, "task_name": t.task_name, "model_type": t.model_type,
        "ts_code": t.ts_code, "predict_steps": t.predict_steps,
        "lookback_window": t.lookback_window,
        "epochs": t.epochs,
        "batch_size": t.batch_size,
        "learning_rate": float(t.learning_rate) if t.learning_rate else None,
        "train_start_date": t.train_start_date,
        "train_end_date": t.train_end_date,
        "val_ratio": float(t.val_ratio) if t.val_ratio else None,
        "test_ratio": float(t.test_ratio) if t.test_ratio else None,
        "status": t.status,
        "current_epoch": t.current_epoch,
        "best_val_loss": float(t.best_val_loss) if t.best_val_loss else None,
        "model_path": t.model_path, "error_msg": t.error_msg,
        "started_at": str(t.started_at) if t.started_at else None,
        "finished_at": str(t.finished_at) if t.finished_at else None,
        "created_at": str(t.created_at) if t.created_at else None,
    }
