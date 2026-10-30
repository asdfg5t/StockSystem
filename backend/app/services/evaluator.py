import numpy as np
import torch
from torch.utils.data import DataLoader
from app.core.data_processor import TimeSeriesProcessor
from app.utils.logger import get_logger

logger = get_logger("evaluate")


def evaluate_model(
    model, loader: DataLoader, processor: TimeSeriesProcessor, device
) -> dict:
    """对模型进行完整评估"""
    model.eval()
    all_preds = []
    all_actuals = []

    with torch.no_grad():
        for X_batch, y_batch in loader:
            X_batch = X_batch.to(device)
            output = model(X_batch)
            all_preds.append(output.cpu().numpy())
            all_actuals.append(y_batch.numpy())

    if not all_preds or not all_actuals:
        logger.warning("评估数据为空, 返回零值指标")
        return {k: 0.0 for k in [
            "mae", "mse", "rmse", "mape", "smape", "r2", "direction_accuracy",
            "max_error", "median_ae", "explained_variance", "pearson_corr",
            "accuracy_1pct", "accuracy_3pct", "accuracy_5pct",
            "win_rate", "profit_factor", "sharpe_ratio", "max_drawdown",
        ]}

    preds = np.concatenate(all_preds, axis=0).flatten()
    actuals = np.concatenate(all_actuals, axis=0).flatten()

    pred_prices = processor.inverse_transform_target(preds)
    actual_prices = processor.inverse_transform_target(actuals)

    metrics = compute_metrics(actual_prices, pred_prices)

    logger.info(
        f"评估结果: MAE={metrics['mae']:.4f} | RMSE={metrics['rmse']:.4f} | "
        f"MAPE={metrics['mape']:.4f}% | R²={metrics['r2']:.4f} | "
        f"准确率[1%]={metrics['accuracy_1pct']:.1f}% "
        f"[3%]={metrics['accuracy_3pct']:.1f}% "
        f"[5%]={metrics['accuracy_5pct']:.1f}% | "
        f"皮尔逊={metrics['pearson_corr']:.4f} | "
        f"夏普={metrics['sharpe_ratio']:.4f}"
    )
    return metrics


def compute_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    """计算完整评估指标集（15项）"""
    actual = np.array(actual, dtype=np.float64)
    predicted = np.array(predicted, dtype=np.float64)
    errors = actual - predicted
    abs_errors = np.abs(errors)

    # --- 基础回归指标 ---
    mae = np.mean(abs_errors)
    mse = np.mean(errors ** 2)
    rmse = np.sqrt(mse)

    non_zero = actual != 0
    if non_zero.sum() > 0:
        mape = np.mean(np.abs(errors[non_zero] / actual[non_zero])) * 100
    else:
        mape = 0.0

    denominator = np.abs(actual) + np.abs(predicted)
    non_zero_denom = denominator != 0
    if non_zero_denom.sum() > 0:
        smape = np.mean(
            2 * np.abs(errors[non_zero_denom]) / denominator[non_zero_denom]
        ) * 100
    else:
        smape = 0.0

    ss_res = np.sum(errors ** 2)
    ss_tot = np.sum((actual - np.mean(actual)) ** 2)
    r2 = 1 - (ss_res / (ss_tot + 1e-8))

    # --- 新增：稳健性指标 ---
    max_error = float(np.max(abs_errors))
    median_ae = float(np.median(abs_errors))

    # 解释方差: 1 - Var(actual - predicted) / Var(actual)
    explained_variance = 1 - (np.var(errors) / (np.var(actual) + 1e-8))

    # 皮尔逊相关系数
    if len(actual) > 1 and np.std(actual) > 1e-8 and np.std(predicted) > 1e-8:
        pearson_corr = float(np.corrcoef(actual, predicted)[0, 1])
    else:
        pearson_corr = 0.0

    # --- 价格预测准确率（误差在阈值内的占比）---
    pct_errors = abs_errors / (np.abs(actual) + 1e-8) * 100
    accuracy_1pct = float(np.mean(pct_errors <= 1.0) * 100)
    accuracy_3pct = float(np.mean(pct_errors <= 3.0) * 100)
    accuracy_5pct = float(np.mean(pct_errors <= 5.0) * 100)

    # --- 交易模拟指标 ---
    if len(actual) > 1:
        actual_returns = np.diff(actual) / (actual[:-1] + 1e-8)

        actual_direction = np.diff(actual) > 0
        predicted_direction = np.diff(predicted) > 0
        direction_accuracy = np.mean(actual_direction == predicted_direction) * 100

        # 胜率：按预测方向交易，实际盈利的比例
        signal = np.where(predicted_direction, 1.0, -1.0)
        strategy_returns = signal * actual_returns
        win_rate = float(np.mean(strategy_returns > 0) * 100)

        # 盈利因子 = 总盈利 / 总亏损
        gains = strategy_returns[strategy_returns > 0]
        losses = strategy_returns[strategy_returns < 0]
        total_gain = np.sum(gains) if len(gains) > 0 else 0.0
        total_loss = np.abs(np.sum(losses)) if len(losses) > 0 else 1e-8
        profit_factor = total_gain / (total_loss + 1e-8)

        # 夏普比率 (年化, 假设252个交易日)
        if np.std(strategy_returns) > 1e-8:
            sharpe_ratio = (np.mean(strategy_returns) / np.std(strategy_returns)) * np.sqrt(252)
        else:
            sharpe_ratio = 0.0

        # 最大回撤
        cumulative = np.cumprod(1 + strategy_returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (running_max - cumulative) / (running_max + 1e-8)
        max_drawdown = float(np.max(drawdown)) * 100
    else:
        direction_accuracy = 0.0
        win_rate = 0.0
        profit_factor = 0.0
        sharpe_ratio = 0.0
        max_drawdown = 0.0

    return {
        "mae": round(float(mae), 6),
        "mse": round(float(mse), 6),
        "rmse": round(float(rmse), 6),
        "mape": round(float(mape), 6),
        "smape": round(float(smape), 6),
        "r2": round(float(r2), 6),
        "direction_accuracy": round(float(direction_accuracy), 4),
        "max_error": round(float(max_error), 6),
        "median_ae": round(float(median_ae), 6),
        "explained_variance": round(float(explained_variance), 6),
        "pearson_corr": round(float(pearson_corr), 6),
        "accuracy_1pct": round(float(accuracy_1pct), 4),
        "accuracy_3pct": round(float(accuracy_3pct), 4),
        "accuracy_5pct": round(float(accuracy_5pct), 4),
        "win_rate": round(float(win_rate), 4),
        "profit_factor": round(float(profit_factor), 6),
        "sharpe_ratio": round(float(sharpe_ratio), 6),
        "max_drawdown": round(float(max_drawdown), 4),
    }
