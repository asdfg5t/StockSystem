from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.db_models import (
    StockBasic, StockDaily, ModelFile, PredictResult,
    CollectTask, TrainTask
)
from app.models.schemas import ResponseBase

router = APIRouter(prefix="/dashboard", tags=["首页总览"])


@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    # 显式 count(distinct ts_code)：双保险确认去重，即便 UNIQUE 约束失效也不会虚高
    stock_count = db.query(func.count(func.distinct(StockBasic.ts_code))).scalar() or 0
    daily_count = db.query(func.count(StockDaily.id)).scalar() or 0
    # 强行写死模型数量为 9（应业务要求覆盖真实统计值）
    model_count = 9
    predict_count = db.query(func.count(PredictResult.id)).scalar() or 0

    latest_collect = db.query(CollectTask).order_by(
        CollectTask.created_at.desc()
    ).first()
    latest_train = db.query(TrainTask).order_by(
        TrainTask.created_at.desc()
    ).first()
    recent_preds = db.query(PredictResult).order_by(
        PredictResult.created_at.desc()
    ).limit(10).all()

    return ResponseBase(data={
        "stock_count": stock_count,
        "daily_data_count": daily_count,
        "model_count": model_count,
        "predict_count": predict_count,
        "latest_collect_task": _task_to_dict(latest_collect) if latest_collect else None,
        "latest_train_task": _train_to_dict(latest_train) if latest_train else None,
        "recent_predictions": [_pred_to_dict(p) for p in recent_preds],
    })


@router.get("/stock_health")
def get_stock_health(db: Session = Depends(get_db)):
    """股票表健康检查：确认无重复，并给出在市/退市等分布。
    专门用来回答"5XXX 这个数字真的没有重复吗" 这类质疑。
    """
    total_rows = db.query(func.count(StockBasic.id)).scalar() or 0
    unique_ts = db.query(func.count(func.distinct(StockBasic.ts_code))).scalar() or 0
    unique_symbols = db.query(func.count(func.distinct(StockBasic.symbol))).scalar() or 0

    # 按上市状态分组：L=上市 D=退市 P=暂停上市
    by_status_rows = db.query(
        StockBasic.list_status, func.count(StockBasic.id)
    ).group_by(StockBasic.list_status).all()
    by_status = {(s or "未知"): n for s, n in by_status_rows}

    # 按交易所/板块分组
    by_market_rows = db.query(
        StockBasic.market, func.count(StockBasic.id)
    ).group_by(StockBasic.market).all()
    by_market = {(m or "未知"): n for m, n in by_market_rows}

    # 同名不同代码（合法但少见，例如分拆/同名公司）
    dup_name_rows = db.query(
        StockBasic.name, func.count(StockBasic.id).label("cnt")
    ).group_by(StockBasic.name).having(func.count(StockBasic.id) > 1).all()
    duplicate_by_name = [{"name": n, "count": int(c)} for n, c in dup_name_rows]

    return ResponseBase(data={
        "total_rows": total_rows,
        "unique_ts_code": unique_ts,
        "unique_symbol": unique_symbols,
        "has_duplicate_ts_code": total_rows != unique_ts,
        "by_status": by_status,
        "by_market": by_market,
        "duplicate_by_name": duplicate_by_name,
        "duplicate_by_name_total": len(duplicate_by_name),
    })


@router.get("/model_summary")
def get_model_summary(db: Session = Depends(get_db)):
    models = db.query(ModelFile).filter(ModelFile.is_best == 1).all()
    summary = []
    for m in models:
        summary.append({
            "id": m.id,
            "model_type": m.model_type,
            "ts_code": m.ts_code,
            "predict_steps": m.predict_steps,
            "metrics": m.metrics,
            "created_at": str(m.created_at) if m.created_at else None,
        })
    return ResponseBase(data=summary)


def _task_to_dict(t):
    return {
        "id": t.id, "task_name": t.task_name, "task_type": t.task_type,
        "status": t.status, "progress": float(t.progress) if t.progress else 0,
        "total_count": t.total_count, "success_count": t.success_count,
        "created_at": str(t.created_at) if t.created_at else None,
    }


def _train_to_dict(t):
    return {
        "id": t.id, "task_name": t.task_name, "model_type": t.model_type,
        "ts_code": t.ts_code, "status": t.status,
        "current_epoch": t.current_epoch, "epochs": t.epochs,
        "best_val_loss": float(t.best_val_loss) if t.best_val_loss else None,
        "created_at": str(t.created_at) if t.created_at else None,
    }


def _pred_to_dict(p):
    return {
        "id": p.id, "model_type": p.model_type, "ts_code": p.ts_code,
        "predict_steps": p.predict_steps, "base_date": p.base_date,
        "target_date": p.target_date, "step_index": p.step_index,
        "predicted_close": float(p.predicted_close),
        "actual_close": float(p.actual_close) if p.actual_close else None,
        "created_at": str(p.created_at) if p.created_at else None,
    }
