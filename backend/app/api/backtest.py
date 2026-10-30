import json
import numpy as np
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.db_models import EvaluateResult, StockDaily
from app.models.schemas import ResponseBase

router = APIRouter(prefix="/backtest", tags=["回测模拟"])


@router.get("/run")
def run_backtest(
    ts_code: str = Query(...),
    model_type: str = Query("BiLSTM"),
    predict_steps: int = Query(1),
    initial_capital: float = Query(100000),
    db: Session = Depends(get_db),
):
    eval_res = None
    for code in [ts_code, "smart_universal", "universal"]:
        eval_res = db.query(EvaluateResult).filter(
            EvaluateResult.ts_code == code,
            EvaluateResult.model_type == model_type,
            EvaluateResult.predict_steps == predict_steps,
            EvaluateResult.dataset_type == "test",
        ).order_by(EvaluateResult.created_at.desc()).first()
        if eval_res and eval_res.actual_values and eval_res.predicted_values:
            break

    if not eval_res or not eval_res.actual_values or not eval_res.predicted_values:
        return ResponseBase(code=404, message="未找到评估数据，请先完成模型训练")

    actual = _parse_json_array(eval_res.actual_values)
    predicted = _parse_json_array(eval_res.predicted_values)

    if len(actual) < 2:
        return ResponseBase(code=400, message="数据量不足以进行回测")

    n = min(len(actual), len(predicted))
    actual = np.array(actual[:n])
    predicted = np.array(predicted[:n])

    dailys = db.query(StockDaily).filter(
        StockDaily.ts_code == ts_code
    ).order_by(StockDaily.trade_date.desc()).limit(n + 10).all()
    dailys.reverse()
    dates = [d.trade_date for d in dailys][-n:]

    capital = initial_capital
    position = 0
    trades = []
    equity_curve = [capital]
    benchmark_start = actual[0]

    for i in range(n - 1):
        pred_direction = predicted[i + 1] > predicted[i] if i + 1 < len(predicted) else predicted[i] > actual[i]
        price = actual[i]
        next_price = actual[i + 1]

        if pred_direction and position == 0:
            shares = int(capital / price / 100) * 100
            if shares > 0:
                cost = shares * price
                capital -= cost
                position = shares
                trades.append({
                    "date": dates[i] if i < len(dates) else str(i),
                    "action": "buy",
                    "price": round(float(price), 2),
                    "shares": shares,
                    "pnl": 0,
                })
        elif not pred_direction and position > 0:
            revenue = position * price
            pnl = revenue - (trades[-1]["price"] * position if trades else 0)
            capital += revenue
            trades.append({
                "date": dates[i] if i < len(dates) else str(i),
                "action": "sell",
                "price": round(float(price), 2),
                "shares": position,
                "pnl": round(float(pnl), 2),
            })
            position = 0

        total_value = capital + position * next_price
        equity_curve.append(round(float(total_value), 2))

    if position > 0:
        capital += position * actual[-1]
        position = 0

    equity = np.array(equity_curve)
    benchmark = initial_capital * (actual / actual[0])
    running_max = np.maximum.accumulate(equity)
    drawdown = (running_max - equity) / (running_max + 1e-8) * 100

    total_return = (equity[-1] - initial_capital) / initial_capital * 100
    bench_return = (actual[-1] - actual[0]) / actual[0] * 100
    n_days = len(equity) - 1
    annual_return = total_return * (252 / max(n_days, 1))

    returns = np.diff(equity) / equity[:-1]
    sharpe = float((np.mean(returns) / (np.std(returns) + 1e-8)) * np.sqrt(252))
    max_dd = float(np.max(drawdown))

    win_trades = [t for t in trades if t["action"] == "sell" and t["pnl"] > 0]
    lose_trades = [t for t in trades if t["action"] == "sell" and t["pnl"] <= 0]
    sell_count = len(win_trades) + len(lose_trades)
    win_rate = len(win_trades) / max(sell_count, 1) * 100

    return ResponseBase(data={
        "trades": trades,
        "equity_curve": equity.tolist(),
        "benchmark_curve": benchmark.tolist(),
        "drawdown_curve": drawdown.tolist(),
        "dates": dates,
        "stats": {
            "initial_capital": initial_capital,
            "final_value": round(float(equity[-1]), 2),
            "total_return": round(float(total_return), 2),
            "benchmark_return": round(float(bench_return), 2),
            "annual_return": round(float(annual_return), 2),
            "sharpe_ratio": round(sharpe, 4),
            "max_drawdown": round(max_dd, 2),
            "total_trades": len(trades),
            "win_rate": round(float(win_rate), 2),
        },
    })


def _parse_json_array(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return []
