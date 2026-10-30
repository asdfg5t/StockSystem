import json
import threading
import torch
import numpy as np
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.config import MODEL_DIR
from app.models.db_models import PredictTask, PredictResult, ModelFile
from app.models.schemas import (
    ResponseBase, PageResponse, PredictTaskCreate, QuickPredictRequest,
)
from app.services.predictor import (
    run_prediction,
    run_quick_prediction,
    resolve_actual_close,
    _to_db_date,
    _to_display_date,
    _count_trading_days,
    _pick_step_for_horizon,
    SUPPORTED_STEPS,
)
from app.services.feature_engineer import compute_features
from app.core.data_processor import TimeSeriesProcessor
from app.services.trainer import _build_model
from app.utils.logger import get_logger

logger = get_logger("predict_api")
router = APIRouter(prefix="/predict", tags=["预测任务"])


@router.post("/create")
def create_predict_task(req: PredictTaskCreate, db: Session = Depends(get_db)):
    predict_steps = req.predict_steps
    predict_date = req.predict_date

    if req.target_date:
        from app.services.feature_engineer import compute_features as _cf
        feat = _cf(db, req.ts_code, save_to_db=False) if not predict_date else None
        if predict_date:
            base_for_count = predict_date
        elif feat is not None and not feat.empty:
            base_for_count = feat["trade_date"].iloc[-1]
        else:
            return ResponseBase(code=400, message="目标日期模式下需先有该股特征数据")
        steps_needed = _count_trading_days(db, req.ts_code, base_for_count, req.target_date)
        if steps_needed <= 0:
            return ResponseBase(code=400, message="目标日期必须晚于基准日且二者间存在交易日")
        if steps_needed > SUPPORTED_STEPS[-1]:
            return ResponseBase(
                code=400,
                message=f"目标距基准 {steps_needed} 个交易日，超出最大步长 {SUPPORTED_STEPS[-1]}",
            )
        predict_steps = _pick_step_for_horizon(steps_needed)
        predict_date = _to_display_date(base_for_count)

    task = PredictTask(
        task_name=req.task_name,
        model_type=req.model_type,
        ts_code=req.ts_code,
        predict_steps=predict_steps,
        model_file_id=req.model_file_id,
        predict_date=predict_date,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return ResponseBase(data={
        "id": task.id,
        "status": task.status,
        "predict_steps": task.predict_steps,
        "predict_date": task.predict_date,
        "target_date": req.target_date,
    })


@router.post("/start/{task_id}")
def start_predict_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(PredictTask).filter(PredictTask.id == task_id).first()
    if not task:
        return ResponseBase(code=404, message="任务不存在")
    if task.status == "running":
        return ResponseBase(code=400, message="任务正在运行中")

    def _run():
        session = SessionLocal()
        try:
            run_prediction(session, task_id)
        finally:
            session.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return ResponseBase(message="预测任务已启动")


@router.post("/quick")
def quick_predict(req: QuickPredictRequest, db: Session = Depends(get_db)):
    """快速预测：
    - 模式 A：传 predict_steps（1/3/5），从 base_date 起预测 N 个交易日
    - 模式 B：传 target_date，自动反推所需步长

    每一步均通过 DB → Tushare 兜底获取实际收盘价并对比。
    预测结果会同步写入 PredictTask + PredictResult，方便在「预测任务 / 预测结果」页面回溯。
    """
    try:
        result = run_quick_prediction(
            db=db,
            ts_code=req.ts_code,
            model_type=req.model_type,
            base_date=req.base_date,
            predict_steps=req.predict_steps,
            target_date=req.target_date,
        )
        return ResponseBase(data=result)
    except ValueError as e:
        return ResponseBase(code=400, message=str(e))
    except Exception as e:
        logger.error(f"快速预测失败: {e}", exc_info=True)
        return ResponseBase(code=500, message=f"快速预测失败: {str(e)[:200]}")


@router.get("/tasks")
def get_predict_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    model_type: str = Query(""),
    status: str = Query(""),
    db: Session = Depends(get_db),
):
    query = db.query(PredictTask)
    if model_type:
        query = query.filter(PredictTask.model_type == model_type)
    if status:
        query = query.filter(PredictTask.status == status)
    total = query.count()
    items = query.order_by(PredictTask.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return PageResponse(
        data=[_task_to_dict(t) for t in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/results")
def get_predict_results(
    task_id: int = Query(0),
    ts_code: str = Query(""),
    model_type: str = Query(""),
    predict_steps: int = Query(0),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(PredictResult)
    if task_id > 0:
        query = query.filter(PredictResult.task_id == task_id)
    if ts_code:
        query = query.filter(PredictResult.ts_code == ts_code)
    if model_type:
        query = query.filter(PredictResult.model_type == model_type)
    if predict_steps > 0:
        query = query.filter(PredictResult.predict_steps == predict_steps)

    total = query.count()
    items = query.order_by(PredictResult.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return PageResponse(
        data=[_result_to_dict(r) for r in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/compare")
def get_prediction_comparison(
    ts_code: str = Query(...),
    predict_steps: int = Query(1),
    db: Session = Depends(get_db),
):
    """多模型预测结果对比"""
    results = {}
    for model_type in ["TFT", "Transformer", "BiLSTM"]:
        preds = db.query(PredictResult).filter(
            PredictResult.ts_code == ts_code,
            PredictResult.model_type == model_type,
            PredictResult.predict_steps == predict_steps,
        ).order_by(PredictResult.created_at.desc()).limit(predict_steps).all()
        results[model_type] = [_result_to_dict(p) for p in preds]

    return ResponseBase(data=results)


@router.post("/backfill_actual")
def backfill_actual_prices(
    use_tushare: bool = Query(True, description="DB 没有时是否调用 Tushare 兜底"),
    limit: int = Query(0, ge=0, le=2000, description="本次最多回填多少条，0=全部"),
    db: Session = Depends(get_db),
):
    """回填所有缺失实际收盘价的预测记录。
    - 优先使用本地 stock_daily 数据
    - 若 DB 无对应日期，使用 Tushare 兜底拉取并写回
    """
    from app.services.predictor import _estimate_trading_dates

    missing_date = db.query(PredictResult).filter(
        PredictResult.actual_close.is_(None),
        (PredictResult.target_date == "") | (PredictResult.target_date.is_(None)),
    ).all()
    for r in missing_date:
        if r.base_date and r.step_index:
            dates = _estimate_trading_dates(r.base_date, r.step_index)
            r.target_date = dates[-1] if dates else ""
    if missing_date:
        db.flush()

    pending_q = db.query(PredictResult).filter(
        PredictResult.actual_close.is_(None),
        PredictResult.target_date != "",
        PredictResult.target_date.isnot(None),
    )
    if limit > 0:
        pending = pending_q.limit(limit).all()
    else:
        pending = pending_q.all()

    updated_db = 0
    updated_tushare = 0
    failed = 0

    for r in pending:
        actual = None
        source = None
        if use_tushare:
            actual, source = resolve_actual_close(db, r.ts_code, r.target_date)
        else:
            from app.models.db_models import StockDaily
            row = db.query(StockDaily).filter(
                StockDaily.ts_code == r.ts_code,
                StockDaily.trade_date == _to_db_date(r.target_date),
            ).first()
            if row and row.close is not None:
                actual = float(row.close)
                source = "db"

        if actual is not None:
            r.actual_close = actual
            r.error = round(float(r.predicted_close) - float(actual), 4)
            if float(actual) != 0:
                r.error_pct = round(r.error / float(actual) * 100, 4)
            if source == "db":
                updated_db += 1
            else:
                updated_tushare += 1
        else:
            failed += 1

    db.commit()
    date_fixed = len(missing_date)
    msg = (
        f"回填完成：补算目标日期 {date_fixed} 条，"
        f"DB 命中 {updated_db} 条，Tushare 兜底 {updated_tushare} 条，"
        f"未找到 {failed} 条"
    )
    return ResponseBase(
        message=msg,
        data={
            "date_fixed": date_fixed,
            "total_pending": len(pending),
            "updated_db": updated_db,
            "updated_tushare": updated_tushare,
            "failed": failed,
            "updated": updated_db + updated_tushare,
        },
    )


@router.delete("/task/{task_id}")
def delete_predict_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(PredictTask).filter(PredictTask.id == task_id).first()
    if not task:
        return ResponseBase(code=404, message="任务不存在")
    db.query(PredictResult).filter(PredictResult.task_id == task_id).delete()
    db.delete(task)
    db.commit()
    return ResponseBase(message="删除成功")


DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


@router.get("/confidence")
def get_prediction_confidence(
    ts_code: str = Query("000001.SZ"),
    model_type: str = Query("BiLSTM"),
    predict_steps: int = Query(1),
    n_samples: int = Query(30, ge=5, le=100),
    db: Session = Depends(get_db),
):
    """Monte Carlo Dropout confidence estimation"""
    model_file = None
    for code in [ts_code, "smart_universal", "universal"]:
        model_file = db.query(ModelFile).filter(
            ModelFile.model_type == model_type,
            ModelFile.ts_code == code,
            ModelFile.predict_steps == predict_steps,
            ModelFile.is_best == 1,
        ).order_by(ModelFile.created_at.desc()).first()
        if model_file:
            break

    if not model_file:
        return ResponseBase(code=404, message="未找到模型文件")

    try:
        if not model_file.scaler_path or not model_file.feature_config:
            return ResponseBase(
                code=400,
                message="模型文件缺少 scaler 或特征配置信息，请重新训练模型",
            )
        scaler_info = json.loads(model_file.scaler_path)
        feature_columns = json.loads(model_file.feature_config)

        processor = TimeSeriesProcessor(lookback=30, predict_steps=predict_steps)
        processor.load_scalers(scaler_info["feature"], scaler_info["target"])
        processor.feature_columns = feature_columns

        feature_df = compute_features(db, ts_code)
        if feature_df.empty:
            return ResponseBase(code=404, message="特征数据为空")

        X = processor.prepare_predict_input(feature_df)
        input_size = X.shape[2]

        model = _build_model(model_type, input_size, predict_steps)
        model.load_state_dict(torch.load(model_file.file_path, map_location=DEVICE))
        model = model.to(DEVICE)
        model.train()

        X_tensor = torch.FloatTensor(X).to(DEVICE)
        all_preds = []
        with torch.no_grad():
            for _ in range(n_samples):
                pred = model(X_tensor).cpu().numpy().flatten()
                prices = processor.inverse_transform_target(pred)
                all_preds.append(prices.tolist())

        all_preds = np.array(all_preds)
        mean_pred = np.mean(all_preds, axis=0)
        std_pred = np.std(all_preds, axis=0)
        upper_95 = mean_pred + 1.96 * std_pred
        lower_95 = mean_pred - 1.96 * std_pred

        return ResponseBase(data={
            "model_type": model_type,
            "ts_code": ts_code,
            "predict_steps": predict_steps,
            "mean_prediction": np.round(mean_pred, 4).tolist(),
            "std_prediction": np.round(std_pred, 4).tolist(),
            "upper_95": np.round(upper_95, 4).tolist(),
            "lower_95": np.round(lower_95, 4).tolist(),
            "n_samples": n_samples,
        })
    except Exception as e:
        return ResponseBase(code=500, message=f"置信区间计算失败: {str(e)[:200]}")


def _task_to_dict(t):
    return {
        "id": t.id, "task_name": t.task_name, "model_type": t.model_type,
        "model_file_id": t.model_file_id, "ts_code": t.ts_code,
        "predict_steps": t.predict_steps, "predict_date": t.predict_date,
        "status": t.status, "error_msg": t.error_msg,
        "started_at": str(t.started_at) if t.started_at else None,
        "finished_at": str(t.finished_at) if t.finished_at else None,
        "created_at": str(t.created_at) if t.created_at else None,
    }


def _result_to_dict(r):
    return {
        "id": r.id, "task_id": r.task_id, "model_type": r.model_type,
        "ts_code": r.ts_code, "predict_steps": r.predict_steps,
        "base_date": r.base_date, "target_date": r.target_date,
        "step_index": r.step_index,
        "predicted_close": float(r.predicted_close),
        "actual_close": float(r.actual_close) if r.actual_close else None,
        "error": float(r.error) if r.error else None,
        "error_pct": float(r.error_pct) if r.error_pct else None,
        "created_at": str(r.created_at) if r.created_at else None,
    }
