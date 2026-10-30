import json
import torch
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.config import MODEL_DIR
from app.models.db_models import (
    PredictTask, PredictResult, ModelFile, StockDaily
)
from app.services.feature_engineer import compute_features
from app.core.data_processor import TimeSeriesProcessor
from app.services.trainer import _build_model
from app.utils.logger import get_logger

logger = get_logger("predict")

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

SUPPORTED_STEPS = (1, 3, 5)


# ===================== 日期工具 =====================
def _to_db_date(s) -> str:
    """统一转成 YYYYMMDD（数据库内的 trade_date 格式）。支持 'YYYY-MM-DD' / 'YYYYMMDD' / datetime。"""
    if s is None:
        return ""
    if hasattr(s, "strftime"):
        return s.strftime("%Y%m%d")
    s = str(s).strip()
    return s.replace("-", "")


def _to_display_date(s) -> str:
    """统一转成 YYYY-MM-DD（前端展示格式）。"""
    if s is None:
        return ""
    if hasattr(s, "strftime"):
        return s.strftime("%Y-%m-%d")
    s = str(s).strip()
    if "-" in s:
        return s
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s


def _pick_step_for_horizon(steps_needed: int) -> int:
    """根据需要预测的交易日数选择最接近的模型 step（1/3/5）。"""
    for step in SUPPORTED_STEPS:
        if steps_needed <= step:
            return step
    return SUPPORTED_STEPS[-1]


# ===================== Tushare 实际收盘价兜底 =====================
def _fetch_daily_from_tushare(ts_code: str, target_date_db: str) -> Optional[dict]:
    """通过 Tushare 拉取单日行情，返回 dict 或 None。target_date_db 格式必须是 YYYYMMDD。"""
    try:
        from app.services.data_collector import _get_tushare_api
        pro = _get_tushare_api()
        df = pro.daily(ts_code=ts_code, start_date=target_date_db, end_date=target_date_db)
        if df is None or df.empty:
            return None
        row = df.iloc[0]
        return {
            "ts_code": row.get("ts_code", ts_code),
            "trade_date": row["trade_date"],
            "open": float(row.get("open")) if row.get("open") is not None else None,
            "high": float(row.get("high")) if row.get("high") is not None else None,
            "low": float(row.get("low")) if row.get("low") is not None else None,
            "close": float(row.get("close")) if row.get("close") is not None else None,
            "pre_close": float(row.get("pre_close")) if row.get("pre_close") is not None else None,
            "change": float(row.get("change")) if row.get("change") is not None else None,
            "pct_chg": float(row.get("pct_chg")) if row.get("pct_chg") is not None else None,
            "vol": float(row.get("vol")) if row.get("vol") is not None else None,
            "amount": float(row.get("amount")) if row.get("amount") is not None else None,
        }
    except Exception as e:
        logger.warning(f"Tushare 拉取 {ts_code} {target_date_db} 失败: {e}")
        return None


def resolve_actual_close(db: Session, ts_code: str, target_date) -> Tuple[Optional[float], Optional[str]]:
    """先查 DB；DB 没有则调用 Tushare 拉取并写回 DB。返回 (close, source)。"""
    if not target_date:
        return None, None
    target_db = _to_db_date(target_date)
    if not target_db:
        return None, None

    actual = db.query(StockDaily).filter(
        StockDaily.ts_code == ts_code,
        StockDaily.trade_date == target_db,
    ).first()
    if actual and actual.close is not None:
        return float(actual.close), "db"

    fetched = _fetch_daily_from_tushare(ts_code, target_db)
    if fetched is None or fetched.get("close") is None:
        return None, None

    try:
        new_row = StockDaily(
            ts_code=ts_code,
            trade_date=fetched["trade_date"],
            open=fetched.get("open"),
            high=fetched.get("high"),
            low=fetched.get("low"),
            close=fetched.get("close"),
            pre_close=fetched.get("pre_close"),
            change=fetched.get("change"),
            pct_chg=fetched.get("pct_chg"),
            vol=fetched.get("vol"),
            amount=fetched.get("amount"),
        )
        db.add(new_row)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Tushare 数据回写 DB 失败（不影响返回）: {e}")

    return float(fetched["close"]), "tushare"


# ===================== 交易日推算 =====================
def _count_trading_days(db: Session, ts_code: str, base_date, target_date) -> int:
    """返回 (base_date, target_date] 之间的交易日数量。优先用本股票数据，再用全市场任意股票，最后退化为周一到周五估算。"""
    base_db = _to_db_date(base_date)
    target_db = _to_db_date(target_date)
    if not base_db or not target_db or target_db <= base_db:
        return 0

    rows = db.query(StockDaily.trade_date).filter(
        StockDaily.ts_code == ts_code,
        StockDaily.trade_date > base_db,
        StockDaily.trade_date <= target_db,
    ).order_by(StockDaily.trade_date.asc()).all()
    if rows:
        return len(rows)

    rows = db.query(StockDaily.trade_date).filter(
        StockDaily.trade_date > base_db,
        StockDaily.trade_date <= target_db,
    ).distinct().all()
    if rows:
        return len(rows)

    base = datetime.strptime(base_db, "%Y%m%d")
    target = datetime.strptime(target_db, "%Y%m%d")
    n = 0
    cur = base + timedelta(days=1)
    while cur <= target:
        if cur.weekday() < 5:
            n += 1
        cur += timedelta(days=1)
    return n


# ===================== 标准预测任务流 =====================
def run_prediction(db: Session, task_id: int):
    """执行预测任务（支持通用模型和单股票模型）"""
    task = db.query(PredictTask).filter(PredictTask.id == task_id).first()
    if not task:
        logger.error(f"预测任务 {task_id} 不存在")
        return
    task.status = "running"
    task.started_at = datetime.now()
    db.commit()

    try:
        model_file = _find_model_file(db, task)
        if not model_file:
            raise ValueError(
                f"未找到 {task.model_type} {task.ts_code} "
                f"步长{task.predict_steps} 的模型文件"
            )

        if not model_file.scaler_path or not model_file.feature_config:
            raise ValueError("模型文件缺少 scaler 或特征配置信息，请重新训练模型")
        scaler_info = json.loads(model_file.scaler_path)
        feature_columns = json.loads(model_file.feature_config)
        is_universal = model_file.ts_code in ("universal", "smart_universal")

        processor = TimeSeriesProcessor(
            lookback=30,
            predict_steps=task.predict_steps,
        )
        processor.load_scalers(scaler_info["feature"], scaler_info["target"])
        processor.feature_columns = feature_columns

        feature_df = compute_features(db, task.ts_code)
        if feature_df.empty:
            raise ValueError(f"股票 {task.ts_code} 特征数据为空")

        X = processor.prepare_predict_input(
            feature_df,
            ts_code=task.ts_code if is_universal else None,
        )
        input_size = X.shape[2]

        model = _build_model(
            task.model_type, input_size, task.predict_steps
        )
        model.load_state_dict(
            torch.load(model_file.file_path, map_location=DEVICE)
        )
        model = model.to(DEVICE)
        model.eval()

        with torch.no_grad():
            pred = model(torch.FloatTensor(X).to(DEVICE))
            pred = pred.cpu().numpy().flatten()

        predicted_prices = processor.inverse_transform_target(pred)

        base_date = task.predict_date or feature_df["trade_date"].iloc[-1]
        trading_dates = _get_future_trading_dates(
            db, task.ts_code, base_date, task.predict_steps
        )

        for i, price in enumerate(predicted_prices):
            target_date = trading_dates[i] if i < len(trading_dates) else ""

            actual_close, _src = resolve_actual_close(db, task.ts_code, target_date)

            error = None
            error_pct = None
            if actual_close is not None:
                error = round(float(price) - actual_close, 4)
                error_pct = round(error / actual_close * 100, 4) if actual_close != 0 else None

            result = PredictResult(
                task_id=task_id,
                model_type=task.model_type,
                ts_code=task.ts_code,
                predict_steps=task.predict_steps,
                base_date=base_date,
                target_date=target_date,
                step_index=i + 1,
                predicted_close=round(float(price), 4),
                actual_close=actual_close,
                error=error,
                error_pct=error_pct,
            )
            db.add(result)

        task.status = "completed"
        task.finished_at = datetime.now()
        db.commit()

        logger.info(
            f"预测完成: {task.model_type} | {task.ts_code} | "
            f"步长={task.predict_steps} | 预测值={predicted_prices.tolist()}"
        )

    except Exception as e:
        error_msg = str(e).replace("{", "{{").replace("}", "}}")
        logger.error(f"预测失败: {error_msg}", exc_info=True)
        try:
            db.rollback()
            task.status = "failed"
            task.error_msg = str(e)[:2000]
            task.finished_at = datetime.now()
            db.commit()
        except Exception:
            pass


# ===================== 快速指定日期预测 =====================
def run_quick_prediction(
    db: Session,
    ts_code: str,
    model_type: str,
    base_date=None,
    predict_steps: Optional[int] = None,
    target_date=None,
) -> dict:
    """快速预测：立即返回结果，并把这一次的 PredictTask + N 条 PredictResult
    写入数据库，方便在「预测任务 / 预测结果」页面里查询和回溯。

    支持两种模式（二选一）：
      A. 指定 predict_steps：直接使用该步长模型，预测从 base_date 起 N 个交易日。
      B. 指定 target_date：自动推算所需步长，并选最合适的 1/3/5 模型。

    每一步预测都会通过 DB → Tushare 兜底获取实际收盘价并对比。
    """
    if not ts_code:
        raise ValueError("缺少股票代码")
    if not model_type:
        raise ValueError("缺少模型类型")
    if not predict_steps and not target_date:
        raise ValueError("请至少指定预测步长或目标日期之一")

    feature_df = compute_features(db, ts_code, save_to_db=False)
    if feature_df.empty:
        raise ValueError(f"股票 {ts_code} 特征数据不足，请先采集行情数据")

    last_feat_date_db = _to_db_date(feature_df["trade_date"].iloc[-1])

    if base_date:
        base_date_db = _to_db_date(base_date)
        sub = feature_df[feature_df["trade_date"].apply(_to_db_date) <= base_date_db]
        if sub.empty:
            raise ValueError(f"基准日 {base_date} 之前无可用特征数据")
        feature_df = sub.reset_index(drop=True)
        actual_base_db = _to_db_date(feature_df["trade_date"].iloc[-1])
    else:
        actual_base_db = last_feat_date_db
    actual_base_disp = _to_display_date(actual_base_db)

    target_idx = None
    requested_target_disp = None

    if predict_steps:
        if predict_steps not in SUPPORTED_STEPS:
            raise ValueError(
                f"预测步长 {predict_steps} 不支持，可选值：{SUPPORTED_STEPS}"
            )
        chosen_step = predict_steps
    else:
        target_date_db = _to_db_date(target_date)
        requested_target_disp = _to_display_date(target_date)
        if target_date_db <= actual_base_db:
            raise ValueError(
                f"目标日期 {requested_target_disp} 必须晚于基准日 {actual_base_disp}"
            )
        steps_needed = _count_trading_days(db, ts_code, actual_base_db, target_date_db)
        if steps_needed <= 0:
            raise ValueError(
                f"基准日 {actual_base_disp} 与目标日 {requested_target_disp} 之间无交易日"
            )
        if steps_needed > SUPPORTED_STEPS[-1]:
            raise ValueError(
                f"目标距基准 {steps_needed} 个交易日，超出当前模型最大支持步长（{SUPPORTED_STEPS[-1]}）"
            )
        chosen_step = _pick_step_for_horizon(steps_needed)
        target_idx = steps_needed - 1

    fake_task = PredictTask(
        model_type=model_type,
        ts_code=ts_code,
        predict_steps=chosen_step,
        model_file_id=None,
    )
    model_file = _find_model_file(db, fake_task)
    if not model_file:
        raise ValueError(
            f"未找到 {model_type} step{chosen_step} 模型文件（请先训练或确认 model_file 表）"
        )
    if not model_file.scaler_path or not model_file.feature_config:
        raise ValueError("模型文件缺少 scaler 或特征配置信息，请重新训练模型")

    scaler_info = json.loads(model_file.scaler_path)
    feature_columns = json.loads(model_file.feature_config)
    is_universal = model_file.ts_code in ("universal", "smart_universal")

    processor = TimeSeriesProcessor(lookback=30, predict_steps=chosen_step)
    processor.load_scalers(scaler_info["feature"], scaler_info["target"])
    processor.feature_columns = feature_columns

    X = processor.prepare_predict_input(
        feature_df,
        ts_code=ts_code if is_universal else None,
    )
    input_size = X.shape[2]

    model = _build_model(model_type, input_size, chosen_step)
    model.load_state_dict(torch.load(model_file.file_path, map_location=DEVICE))
    model = model.to(DEVICE)
    model.eval()

    with torch.no_grad():
        pred = model(torch.FloatTensor(X).to(DEVICE)).cpu().numpy().flatten()
    predicted_prices = processor.inverse_transform_target(pred)

    trading_dates = _get_future_trading_dates(db, ts_code, actual_base_db, chosen_step)

    base_close_row = db.query(StockDaily).filter(
        StockDaily.ts_code == ts_code,
        StockDaily.trade_date == actual_base_db,
    ).first()
    base_close = float(base_close_row.close) if base_close_row and base_close_row.close else None

    all_steps = []
    verified_count = 0
    for i, price in enumerate(predicted_prices):
        d_raw = trading_dates[i] if i < len(trading_dates) else ""
        d_disp = _to_display_date(d_raw)
        actual_close, actual_source = (None, None)
        if d_disp:
            actual_close, actual_source = resolve_actual_close(db, ts_code, d_disp)

        predicted_val = round(float(price), 4)
        error = None
        error_pct = None
        change_pct = None
        if actual_close is not None:
            verified_count += 1
            error = round(predicted_val - actual_close, 4)
            if actual_close != 0:
                error_pct = round(error / actual_close * 100, 4)
        if base_close and base_close != 0:
            change_pct = round((predicted_val - base_close) / base_close * 100, 4)

        all_steps.append({
            "step_index": i + 1,
            "target_date": d_disp,
            "predicted_close": predicted_val,
            "actual_close": round(actual_close, 4) if actual_close is not None else None,
            "actual_source": actual_source,
            "error": error,
            "error_pct": error_pct,
            "change_pct": change_pct,
        })

    if target_idx is None:
        target_idx = chosen_step - 1
    target_step = all_steps[target_idx] if 0 <= target_idx < len(all_steps) else all_steps[-1]

    # 写入 DB，让本次"快速预测"也能在「预测任务 / 预测结果」页面被检索到
    saved_task_id = _persist_quick_prediction(
        db=db,
        ts_code=ts_code,
        model_type=model_type,
        model_file_id=model_file.id,
        chosen_step=chosen_step,
        actual_base_disp=actual_base_disp,
        all_steps=all_steps,
    )

    return {
        "ts_code": ts_code,
        "model_type": model_type,
        "model_step": chosen_step,
        "model_file_id": model_file.id,
        "model_file_path": model_file.file_path,
        "is_universal_model": is_universal,
        "base_date": actual_base_disp,
        "base_close": round(base_close, 4) if base_close is not None else None,
        "target_date": target_step["target_date"],
        "requested_target_date": requested_target_disp,
        "steps_total": chosen_step,
        "verified_count": verified_count,
        "predicted_close": target_step["predicted_close"],
        "actual_close": target_step["actual_close"],
        "actual_source": target_step["actual_source"],
        "error": target_step["error"],
        "error_pct": target_step["error_pct"],
        "all_steps": all_steps,
        "task_id": saved_task_id,
    }


def _persist_quick_prediction(
    db: Session,
    ts_code: str,
    model_type: str,
    model_file_id: int,
    chosen_step: int,
    actual_base_disp: str,
    all_steps: list,
) -> Optional[int]:
    """把一次快速预测结果写入 PredictTask + PredictResult。
    失败不抛错，只记 warning，避免影响返回给前端的预测结果。"""
    try:
        now = datetime.now()
        task = PredictTask(
            task_name=f"快速预测-{ts_code}-{model_type}-step{chosen_step}-{now.strftime('%Y%m%d%H%M%S')}",
            model_type=model_type,
            ts_code=ts_code,
            predict_steps=chosen_step,
            model_file_id=model_file_id,
            predict_date=actual_base_disp,
            status="completed",
            started_at=now,
            finished_at=now,
        )
        db.add(task)
        db.flush()

        for s in all_steps:
            db.add(PredictResult(
                task_id=task.id,
                model_type=model_type,
                ts_code=ts_code,
                predict_steps=chosen_step,
                base_date=actual_base_disp,
                target_date=s.get("target_date") or "",
                step_index=s.get("step_index"),
                predicted_close=s.get("predicted_close"),
                actual_close=s.get("actual_close"),
                error=s.get("error"),
                error_pct=s.get("error_pct"),
            ))

        db.commit()
        logger.info(
            f"快速预测已入库: task_id={task.id} | {model_type}/{ts_code}/step{chosen_step} | "
            f"共 {len(all_steps)} 步"
        )
        return task.id
    except Exception as e:
        logger.warning(f"快速预测入库失败（不影响接口返回）: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return None


def _find_model_file(db: Session, task: PredictTask) -> ModelFile:
    """按优先级查找模型：指定ID > 智能通用模型 > 通用模型 > 单股票模型"""
    if task.model_file_id:
        return db.query(ModelFile).filter(ModelFile.id == task.model_file_id).first()

    for universal_code in ["smart_universal", "universal"]:
        found = db.query(ModelFile).filter(
            ModelFile.model_type == task.model_type,
            ModelFile.ts_code == universal_code,
            ModelFile.predict_steps == task.predict_steps,
            ModelFile.is_best == 1,
        ).order_by(ModelFile.created_at.desc()).first()
        if found:
            return found

    return db.query(ModelFile).filter(
        ModelFile.model_type == task.model_type,
        ModelFile.ts_code == task.ts_code,
        ModelFile.predict_steps == task.predict_steps,
        ModelFile.is_best == 1,
    ).order_by(ModelFile.created_at.desc()).first()


def _get_future_trading_dates(
    db: Session, ts_code: str, base_date, steps: int
) -> list:
    base_db = _to_db_date(base_date)
    dates = db.query(StockDaily.trade_date).filter(
        StockDaily.ts_code == ts_code,
        StockDaily.trade_date > base_db,
    ).order_by(StockDaily.trade_date.asc()).limit(steps).all()
    result = [d.trade_date for d in dates]

    if len(result) < steps:
        result = _estimate_trading_dates(base_db, steps)
    return result


def _estimate_trading_dates(base_date, steps: int) -> list:
    """根据基准日期估算未来交易日（跳过周末）。返回 YYYYMMDD 格式。"""
    base_db = _to_db_date(base_date)
    dt = datetime.strptime(base_db, "%Y%m%d")
    result = []
    while len(result) < steps:
        dt += timedelta(days=1)
        if dt.weekday() < 5:
            result.append(dt.strftime("%Y%m%d"))
    return result
