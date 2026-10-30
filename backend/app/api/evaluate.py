from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.db_models import EvaluateResult
from app.models.schemas import ResponseBase

router = APIRouter(prefix="/evaluate", tags=["模型评估"])


@router.get("/results")
def get_evaluate_results(
    model_type: str = Query(""),
    ts_code: str = Query(""),
    predict_steps: int = Query(0),
    dataset_type: str = Query("test"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(EvaluateResult)
    if model_type:
        query = query.filter(EvaluateResult.model_type == model_type)
    if ts_code:
        query = query.filter(EvaluateResult.ts_code == ts_code)
    if predict_steps > 0:
        query = query.filter(EvaluateResult.predict_steps == predict_steps)
    if dataset_type:
        query = query.filter(EvaluateResult.dataset_type == dataset_type)

    total = query.count()
    items = query.order_by(EvaluateResult.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return ResponseBase(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_eval_to_dict(e) for e in items],
    })


@router.get("/compare")
def compare_models(
    ts_code: str = Query(...),
    predict_steps: int = Query(0),
    db: Session = Depends(get_db),
):
    """三模型对比评估 — 自动回退到智能通用/通用模型"""
    comparison = {}
    for model_type in ["TFT", "Transformer", "BiLSTM"]:
        results = []
        for code in [ts_code, "smart_universal", "universal"]:
            query = db.query(EvaluateResult).filter(
                EvaluateResult.ts_code == code,
                EvaluateResult.model_type == model_type,
                EvaluateResult.dataset_type == "test",
            )
            if predict_steps > 0:
                query = query.filter(EvaluateResult.predict_steps == predict_steps)
            results = query.order_by(EvaluateResult.created_at.desc()).all()
            if results:
                break
        comparison[model_type] = [_eval_to_dict(e) for e in results]

    return ResponseBase(data=comparison)


@router.get("/steps_compare")
def compare_predict_steps(
    ts_code: str = Query(...),
    model_type: str = Query(""),
    db: Session = Depends(get_db),
):
    """不同预测步长对比 — 自动回退到智能通用/通用模型"""
    result = {}
    model_types = [model_type] if model_type else ["TFT", "Transformer", "BiLSTM"]

    for mt in model_types:
        result[mt] = {}
        for steps in [1, 3, 5]:
            eval_res = None
            for code in [ts_code, "smart_universal", "universal"]:
                eval_res = db.query(EvaluateResult).filter(
                    EvaluateResult.ts_code == code,
                    EvaluateResult.model_type == mt,
                    EvaluateResult.predict_steps == steps,
                    EvaluateResult.dataset_type == "test",
                ).order_by(EvaluateResult.created_at.desc()).first()
                if eval_res:
                    break
            if eval_res:
                result[mt][steps] = _eval_to_dict(eval_res)

    return ResponseBase(data=result)


@router.get("/detail/{eval_id}")
def get_evaluate_detail(eval_id: int, db: Session = Depends(get_db)):
    e = db.query(EvaluateResult).filter(EvaluateResult.id == eval_id).first()
    if not e:
        return ResponseBase(code=404, message="评估结果不存在")
    return ResponseBase(data=_eval_to_dict(e))


def _eval_to_dict(e):
    def _f(v):
        return float(v) if v is not None else None

    return {
        "id": e.id,
        "train_task_id": e.train_task_id,
        "model_type": e.model_type,
        "ts_code": e.ts_code,
        "predict_steps": e.predict_steps,
        "dataset_type": e.dataset_type,
        "mae": _f(e.mae),
        "mse": _f(e.mse),
        "rmse": _f(e.rmse),
        "mape": _f(e.mape),
        "smape": _f(e.smape),
        "r2": _f(e.r2),
        "direction_accuracy": _f(e.direction_accuracy),
        "max_error": _f(e.max_error),
        "median_ae": _f(e.median_ae),
        "explained_variance": _f(e.explained_variance),
        "pearson_corr": _f(e.pearson_corr),
        "accuracy_1pct": _f(e.accuracy_1pct),
        "accuracy_3pct": _f(e.accuracy_3pct),
        "accuracy_5pct": _f(e.accuracy_5pct),
        "win_rate": _f(e.win_rate),
        "profit_factor": _f(e.profit_factor),
        "sharpe_ratio": _f(e.sharpe_ratio),
        "max_drawdown": _f(e.max_drawdown),
        "actual_values": e.actual_values,
        "predicted_values": e.predicted_values,
        "created_at": str(e.created_at) if e.created_at else None,
    }
