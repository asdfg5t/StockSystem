"""
论文专用训练脚本
仅对第一只股票训练 BiLSTM / Transformer / TFT 三个模型，各100轮
所有产出（模型、指标、scaler）保存到 paper_output/ 目录，不影响原有数据
"""
import sys
import os
import json
import gc
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
OUTPUT_DIR = BASE_DIR / "paper_output"
MODEL_SAVE_DIR = OUTPUT_DIR / "models"
RESULT_SAVE_DIR = OUTPUT_DIR / "results"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MODEL_SAVE_DIR.mkdir(parents=True, exist_ok=True)
RESULT_SAVE_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))

from app.database import SessionLocal
from app.models.db_models import StockBasic
from app.services.feature_engineer import compute_features
from app.core.data_processor import TimeSeriesProcessor
from app.services.trainer import _build_model
from app.services.evaluator import compute_metrics
import joblib

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

EPOCHS = 100
BATCH_SIZE = 32
LEARNING_RATE = 0.001
LOOKBACK = 30
PREDICT_STEPS_LIST = [1, 3, 5]
MODELS = ["BiLSTM", "Transformer", "TFT"]
EARLY_STOP = False


def train_one_model(feature_df, model_type, ts_code, predict_steps):
    print(f"\n{'─'*50}")
    print(f"  模型: {model_type} | 股票: {ts_code} | 步长: {predict_steps}天 | 轮数: {EPOCHS}")
    print(f"{'─'*50}")

    processor = TimeSeriesProcessor(
        lookback=LOOKBACK, predict_steps=predict_steps,
        pca_components=25, val_ratio=0.15, test_ratio=0.15,
    )
    train_X, train_y, val_X, val_y, test_X, test_y = processor.prepare_data(feature_df)

    print(f"  数据: 训练={len(train_X)} 验证={len(val_X)} 测试={len(test_X)} 特征维度={train_X.shape[2]}")

    input_size = train_X.shape[2]
    model = _build_model(model_type, input_size, predict_steps)
    model = model.to(DEVICE)

    param_count = sum(p.numel() for p in model.parameters())
    print(f"  模型参数量: {param_count:,}")

    train_loader = DataLoader(
        TensorDataset(torch.from_numpy(train_X), torch.from_numpy(train_y)),
        batch_size=BATCH_SIZE, shuffle=True,
    )
    val_loader = DataLoader(
        TensorDataset(torch.from_numpy(val_X), torch.from_numpy(val_y)),
        batch_size=BATCH_SIZE, shuffle=False,
    )

    criterion = nn.SmoothL1Loss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(optimizer, T_0=10, T_mult=2, eta_min=1e-6)

    model_path = str(MODEL_SAVE_DIR / f"{ts_code}_{model_type}_step{predict_steps}_best.pth")
    best_val_loss = float("inf")
    patience_counter = 0
    epoch_metrics = []

    for epoch in range(1, EPOCHS + 1):
        model.train()
        tl, tm, tms, tc = 0, 0, 0, 0
        for xb, yb in train_loader:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            out = model(xb)
            loss = criterion(out, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            bn = len(xb)
            tl += loss.item() * bn
            tm += torch.mean(torch.abs(out - yb)).item() * bn
            tms += torch.mean((out - yb) ** 2).item() * bn
            tc += bn

        train_loss = tl / tc
        train_mae = tm / tc
        train_rmse = (tms / tc) ** 0.5

        if np.isnan(train_loss):
            continue

        model.eval()
        vl, vm, vms, vc = 0, 0, 0, 0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(DEVICE), yb.to(DEVICE)
                out = model(xb)
                loss = criterion(out, yb)
                bn = len(xb)
                vl += loss.item() * bn
                vm += torch.mean(torch.abs(out - yb)).item() * bn
                vms += torch.mean((out - yb) ** 2).item() * bn
                vc += bn

        val_loss = vl / max(vc, 1)
        val_mae = vm / max(vc, 1)
        val_rmse = (vms / max(vc, 1)) ** 0.5

        if np.isnan(val_loss):
            continue

        scheduler.step()
        current_lr = optimizer.param_groups[0]["lr"]

        epoch_metrics.append({
            "epoch": epoch,
            "train_loss": round(train_loss, 6),
            "val_loss": round(val_loss, 6),
            "train_mae": round(train_mae, 6),
            "val_mae": round(val_mae, 6),
            "train_rmse": round(train_rmse, 6),
            "val_rmse": round(val_rmse, 6),
            "learning_rate": current_lr,
        })

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), model_path)

        if epoch % 20 == 0 or epoch == 1 or epoch == EPOCHS:
            print(f"  Epoch {epoch:>3}/{EPOCHS} | "
                  f"TL={train_loss:.5f} VL={val_loss:.5f} | "
                  f"T_MAE={train_mae:.5f} V_MAE={val_mae:.5f} | "
                  f"Best={best_val_loss:.5f}")

    if not os.path.exists(model_path):
        print(f"  ✗ {model_type} 未产生有效模型")
        return None

    model.load_state_dict(torch.load(model_path, map_location=DEVICE, weights_only=True))
    model.eval()

    all_preds, all_actuals = [], []
    test_loader = DataLoader(
        TensorDataset(torch.from_numpy(test_X), torch.from_numpy(test_y)),
        batch_size=BATCH_SIZE, shuffle=False,
    )
    with torch.no_grad():
        for xb, yb in test_loader:
            xb = xb.to(DEVICE)
            out = model(xb)
            all_preds.append(out.cpu().numpy())
            all_actuals.append(yb.numpy())

    preds = np.concatenate(all_preds, axis=0).flatten()
    actuals = np.concatenate(all_actuals, axis=0).flatten()

    pred_returns = processor.target_scaler.inverse_transform(
        preds.reshape(-1, predict_steps)).flatten()
    actual_returns = processor.target_scaler.inverse_transform(
        actuals.reshape(-1, predict_steps)).flatten()
    return_metrics = compute_metrics(actual_returns, pred_returns)

    pred_prices = processor.inverse_transform_target(preds)
    actual_prices = processor.inverse_transform_target(actuals)
    price_metrics = compute_metrics(actual_prices, pred_prices)

    metrics = {}
    for k, v in price_metrics.items():
        metrics[f"price_{k}"] = v
    for k, v in return_metrics.items():
        metrics[f"return_{k}"] = v

    prefix = f"{ts_code}_{model_type}_step{predict_steps}"
    joblib.dump(processor.feature_scaler, str(MODEL_SAVE_DIR / f"{prefix}_feature_scaler.pkl"))
    joblib.dump(processor.target_scaler, str(MODEL_SAVE_DIR / f"{prefix}_target_scaler.pkl"))
    if processor.pca is not None:
        joblib.dump(processor.pca, str(MODEL_SAVE_DIR / f"{prefix}_pca.pkl"))

    result = {
        "ts_code": ts_code,
        "model_type": model_type,
        "predict_steps": predict_steps,
        "epochs_run": len(epoch_metrics),
        "epochs_max": EPOCHS,
        "best_val_loss": round(best_val_loss, 6),
        "param_count": param_count,
        "train_samples": len(train_X),
        "val_samples": len(val_X),
        "test_samples": len(test_X),
        "epoch_metrics": epoch_metrics,
        "test_evaluation": metrics,
        "actual_prices": actual_prices.tolist(),
        "predicted_prices": pred_prices.tolist(),
    }

    result_path = RESULT_SAVE_DIR / f"{model_type}_step{predict_steps}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n  ✓ {model_type} 训练完成:")
    print(f"    [价格] MAE={metrics['price_mae']:.4f} | RMSE={metrics['price_rmse']:.4f} | "
          f"MAPE={metrics['price_mape']:.2f}% | R²={metrics['price_r2']:.4f}")
    print(f"    [收益率] MAE={metrics['return_mae']:.6f} | RMSE={metrics['return_rmse']:.6f} | "
          f"R²={metrics['return_r2']:.4f}")
    print(f"    1%准确率={metrics['price_accuracy_1pct']:.1f}% | "
          f"3%准确率={metrics['price_accuracy_3pct']:.1f}% | "
          f"5%准确率={metrics['price_accuracy_5pct']:.1f}%")
    print(f"    模型: {model_path}")
    print(f"    指标: {result_path}")

    del model, train_loader, val_loader, test_loader
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return metrics


def main():
    start_time = datetime.now()

    print(f"\n{'='*60}")
    print(f"  论文专用训练 | {EPOCHS}轮 | 设备: {DEVICE}")
    print(f"  模型: {', '.join(MODELS)} | 步长: {PREDICT_STEPS_LIST}")
    print(f"  总任务数: {len(MODELS)} × {len(PREDICT_STEPS_LIST)} = {len(MODELS)*len(PREDICT_STEPS_LIST)} 个")
    print(f"  输出目录: {OUTPUT_DIR}")
    print(f"{'='*60}")

    db = SessionLocal()
    try:
        stock = db.query(StockBasic).filter(StockBasic.list_status == "L").order_by(StockBasic.ts_code).first()
        if not stock:
            print("  未找到在市股票，请先运行数据采集")
            return

        ts_code = stock.ts_code
        print(f"\n  目标股票: {ts_code} ({stock.name})")

        feature_df = compute_features(db, ts_code)
        if feature_df.empty:
            print(f"  {ts_code} 特征数据为空，请先采集数据")
            return

        print(f"  特征数据: {len(feature_df)}条 × {len(feature_df.columns)}维")

        all_metrics = {}
        task_idx = 0
        total_tasks = len(MODELS) * len(PREDICT_STEPS_LIST)

        for predict_steps in PREDICT_STEPS_LIST:
            all_metrics[predict_steps] = {}
            for model_type in MODELS:
                task_idx += 1
                print(f"\n  ===== 任务 {task_idx}/{total_tasks} =====")
                metrics = train_one_model(feature_df, model_type, ts_code, predict_steps)
                if metrics:
                    all_metrics[predict_steps][model_type] = metrics

        metric_names = [
            ("价格MAE", "price_mae"),
            ("价格RMSE", "price_rmse"),
            ("价格MAPE(%)", "price_mape"),
            ("价格R²", "price_r2"),
            ("收益率MAE", "return_mae"),
            ("收益率RMSE", "return_rmse"),
            ("收益率R²", "return_r2"),
            ("1%准确率(%)", "price_accuracy_1pct"),
            ("3%准确率(%)", "price_accuracy_3pct"),
            ("5%准确率(%)", "price_accuracy_5pct"),
            ("夏普比率", "price_sharpe_ratio"),
        ]

        summary = {
            "ts_code": ts_code,
            "stock_name": stock.name,
            "predict_steps_list": PREDICT_STEPS_LIST,
            "epochs": EPOCHS,
            "device": str(DEVICE),
            "started": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "finished": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": (datetime.now() - start_time).total_seconds(),
            "comparison": {},
        }

        for predict_steps in PREDICT_STEPS_LIST:
            step_metrics = all_metrics.get(predict_steps, {})
            print(f"\n{'='*60}")
            print(f"  三模型对比 — {predict_steps}天预测 ({ts_code})")
            print(f"{'─'*60}")
            print(f"  {'指标':<14} {'BiLSTM':>10} {'Transformer':>12} {'TFT':>10}")
            print(f"{'─'*60}")

            step_summary = {}
            for display_name, key in metric_names:
                vals = []
                for m in MODELS:
                    v = step_metrics.get(m, {}).get(key, 0)
                    vals.append(v)
                step_summary[key] = {m: step_metrics.get(m, {}).get(key) for m in MODELS}
                print(f"  {display_name:<14} {vals[0]:>10.4f} {vals[1]:>12.4f} {vals[2]:>10.4f}")

            summary["comparison"][f"step{predict_steps}"] = step_summary
            print(f"{'='*60}")

        with open(RESULT_SAVE_DIR / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n  总耗时: {elapsed/60:.1f}分钟")
        print(f"  模型保存: {MODEL_SAVE_DIR}")
        print(f"  指标保存: {RESULT_SAVE_DIR}")
        print(f"  文件列表:")
        for f in sorted(OUTPUT_DIR.rglob("*")):
            if f.is_file():
                size = f.stat().st_size
                unit = "KB" if size < 1024*1024 else "MB"
                val = size/1024 if unit == "KB" else size/1024/1024
                print(f"    {f.relative_to(OUTPUT_DIR)} ({val:.1f}{unit})")

    finally:
        db.close()


if __name__ == "__main__":
    main()
