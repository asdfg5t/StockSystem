"""
逐股训练脚本 — 对每只A股分别训练 BiLSTM/Transformer/TFT 三个模型
每只股票 × 3模型 × 3步长 = 9个任务，每个50轮
训练指标保存到数据库 + 本地 JSON
"""
import sys
import os
import json
import gc
import pymysql
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
RESULT_DIR = BASE_DIR / "train_results"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))

from app.config import MODEL_DIR, settings
from app.database import SessionLocal
from app.models.db_models import StockBasic, TrainTask, TrainMetric, EvaluateResult, ModelFile
from app.services.feature_engineer import compute_features
from app.core.data_processor import TimeSeriesProcessor
from app.services.trainer import _build_model
from app.services.evaluator import evaluate_model, compute_metrics
from app.utils.logger import get_logger

logger = get_logger("train")
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

EPOCHS = 50
BATCH_SIZE = 32
LEARNING_RATE = 0.001
LOOKBACK = 30
MODELS = ["BiLSTM", "Transformer", "TFT"]
PREDICT_STEPS = [1, 3, 5]


def ensure_db_columns():
    conn = pymysql.connect(
        host=settings.DB_HOST, port=settings.DB_PORT,
        user=settings.DB_USER, password=settings.DB_PASSWORD,
        database=settings.DB_NAME, charset="utf8mb4",
    )
    cursor = conn.cursor()
    for sql in [
        "ALTER TABLE train_metric ADD COLUMN train_rmse DECIMAL(12,6) DEFAULT NULL AFTER val_mae",
        "ALTER TABLE train_metric ADD COLUMN val_rmse DECIMAL(12,6) DEFAULT NULL AFTER train_rmse",
        "ALTER TABLE evaluate_result ADD COLUMN max_error DECIMAL(12,6) DEFAULT NULL AFTER direction_accuracy",
        "ALTER TABLE evaluate_result ADD COLUMN median_ae DECIMAL(12,6) DEFAULT NULL AFTER max_error",
        "ALTER TABLE evaluate_result ADD COLUMN explained_variance DECIMAL(12,6) DEFAULT NULL AFTER median_ae",
        "ALTER TABLE evaluate_result ADD COLUMN pearson_corr DECIMAL(12,6) DEFAULT NULL AFTER explained_variance",
        "ALTER TABLE evaluate_result ADD COLUMN accuracy_1pct DECIMAL(8,4) DEFAULT NULL AFTER pearson_corr",
        "ALTER TABLE evaluate_result ADD COLUMN accuracy_3pct DECIMAL(8,4) DEFAULT NULL AFTER accuracy_1pct",
        "ALTER TABLE evaluate_result ADD COLUMN accuracy_5pct DECIMAL(8,4) DEFAULT NULL AFTER accuracy_3pct",
        "ALTER TABLE evaluate_result ADD COLUMN win_rate DECIMAL(8,4) DEFAULT NULL AFTER accuracy_5pct",
        "ALTER TABLE evaluate_result ADD COLUMN profit_factor DECIMAL(12,6) DEFAULT NULL AFTER win_rate",
        "ALTER TABLE evaluate_result ADD COLUMN sharpe_ratio DECIMAL(12,6) DEFAULT NULL AFTER profit_factor",
        "ALTER TABLE evaluate_result ADD COLUMN max_drawdown DECIMAL(8,4) DEFAULT NULL AFTER sharpe_ratio",
    ]:
        try:
            cursor.execute(sql)
        except Exception:
            pass
    conn.commit()
    cursor.close()
    conn.close()


def train_single_stock(db, ts_code, model_type, predict_steps):
    """训练单只股票的单个模型"""
    task_name = f"{model_type}-{ts_code}-{predict_steps}天"

    feature_df = compute_features(db, ts_code)
    if feature_df.empty or len(feature_df) < LOOKBACK + predict_steps + 20:
        logger.warning(f"  {ts_code} 数据不足, 跳过")
        return None

    processor = TimeSeriesProcessor(
        lookback=LOOKBACK, predict_steps=predict_steps,
        pca_components=25, val_ratio=0.15, test_ratio=0.15,
    )
    train_X, train_y, val_X, val_y, test_X, test_y = processor.prepare_data(feature_df)

    if len(train_X) < 10 or len(val_X) < 2 or len(test_X) < 2:
        logger.warning(f"  {ts_code} 序列不足, 跳过")
        return None

    input_size = train_X.shape[2]
    model = _build_model(model_type, input_size, predict_steps)
    model = model.to(DEVICE)

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

    model_save_path = str(MODEL_DIR / f"{ts_code}_{model_type}_step{predict_steps}_best.pth")
    checkpoint_path = str(MODEL_DIR / f"{ts_code}_{model_type}_step{predict_steps}_checkpoint.pth")
    best_val_loss = float("inf")
    start_epoch = 1

    existing_task = db.query(TrainTask).filter(
        TrainTask.model_type == model_type,
        TrainTask.ts_code == ts_code,
        TrainTask.predict_steps == predict_steps,
        TrainTask.status.in_(["running", "completed"]),
    ).order_by(TrainTask.id.desc()).first()

    if existing_task and os.path.exists(checkpoint_path):
        ckpt = torch.load(checkpoint_path, map_location=DEVICE)
        model.load_state_dict(ckpt["model_state"])
        optimizer.load_state_dict(ckpt["optimizer_state"])
        scheduler.load_state_dict(ckpt["scheduler_state"])
        start_epoch = ckpt["epoch"] + 1
        best_val_loss = ckpt.get("best_val_loss", float("inf"))

        task = existing_task
        task.status = "running"
        task_id = task.id
        db.commit()
        print(f"    ★ 断点续训: 从Epoch {start_epoch}继续 (task_id={task_id})")
    else:
        task = TrainTask(
            task_name=task_name, model_type=model_type, ts_code=ts_code,
            predict_steps=predict_steps, lookback_window=LOOKBACK,
            epochs=EPOCHS, batch_size=BATCH_SIZE, learning_rate=LEARNING_RATE,
            val_ratio=0.15, test_ratio=0.15, status="running", started_at=datetime.now(),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id

    if start_epoch > EPOCHS:
        print(f"    已完成全部{EPOCHS}轮, 跳过")
        return None

    for epoch in range(start_epoch, EPOCHS + 1):
        # --- Train ---
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

        # --- Val ---
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

        db.add(TrainMetric(
            task_id=task_id, epoch=epoch,
            train_loss=round(train_loss, 6), val_loss=round(val_loss, 6),
            train_mae=round(train_mae, 6), val_mae=round(val_mae, 6),
            train_rmse=round(train_rmse, 6), val_rmse=round(val_rmse, 6),
            learning_rate=current_lr,
        ))
        task.current_epoch = epoch
        db.commit()

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), model_save_path)
            task.best_val_loss = round(best_val_loss, 6)
            db.commit()

        torch.save({
            "epoch": epoch,
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
            "scheduler_state": scheduler.state_dict(),
            "best_val_loss": best_val_loss,
        }, checkpoint_path)

        if epoch % 10 == 0 or epoch == EPOCHS:
            print(f"\r      Epoch {epoch}/{EPOCHS} | TL={train_loss:.4f} VL={val_loss:.4f} Best={best_val_loss:.4f}", end="", flush=True)
    print()

    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)

    # --- Evaluate ---
    if not os.path.exists(model_save_path):
        task.status = "failed"
        task.error_msg = "未保存有效模型"
        task.finished_at = datetime.now()
        db.commit()
        return None

    model.load_state_dict(torch.load(model_save_path, map_location=DEVICE))
    model.eval()

    test_loader = DataLoader(
        TensorDataset(torch.from_numpy(test_X), torch.from_numpy(test_y)),
        batch_size=BATCH_SIZE, shuffle=False,
    )
    metrics = evaluate_model(model, test_loader, processor, DEVICE)

    actual = processor.inverse_transform_target(test_y.flatten())
    with torch.no_grad():
        preds_list = []
        for i in range(0, len(test_X), BATCH_SIZE):
            batch = torch.from_numpy(test_X[i:i+BATCH_SIZE]).to(DEVICE)
            preds_list.append(model(batch).cpu().numpy())
    preds = np.concatenate(preds_list, axis=0).flatten()
    predicted = processor.inverse_transform_target(preds)

    # Save evaluate result
    db.add(EvaluateResult(
        train_task_id=task_id, model_type=model_type,
        ts_code=ts_code, predict_steps=predict_steps, dataset_type="test",
        mae=metrics.get("mae"), mse=metrics.get("mse"), rmse=metrics.get("rmse"),
        mape=metrics.get("mape"), smape=metrics.get("smape"), r2=metrics.get("r2"),
        direction_accuracy=metrics.get("direction_accuracy"),
        max_error=metrics.get("max_error"), median_ae=metrics.get("median_ae"),
        explained_variance=metrics.get("explained_variance"),
        pearson_corr=metrics.get("pearson_corr"),
        accuracy_1pct=metrics.get("accuracy_1pct"),
        accuracy_3pct=metrics.get("accuracy_3pct"),
        accuracy_5pct=metrics.get("accuracy_5pct"),
        win_rate=metrics.get("win_rate"), profit_factor=metrics.get("profit_factor"),
        sharpe_ratio=metrics.get("sharpe_ratio"), max_drawdown=metrics.get("max_drawdown"),
        actual_values=json.dumps(actual.tolist()),
        predicted_values=json.dumps(predicted.tolist()),
    ))

    # Save model file record
    feat_path, target_path = processor.save_scalers(ts_code, model_type, predict_steps)
    file_size = os.path.getsize(model_save_path) if os.path.exists(model_save_path) else 0
    db.add(ModelFile(
        train_task_id=task_id, model_type=model_type,
        ts_code=ts_code, predict_steps=predict_steps,
        file_path=model_save_path,
        scaler_path=json.dumps({"feature": feat_path, "target": target_path}),
        feature_config=json.dumps(processor.feature_columns),
        metrics=json.dumps(metrics), is_best=1, file_size=file_size,
    ))

    task.status = "completed"
    task.model_path = model_save_path
    task.finished_at = datetime.now()
    db.commit()

    # Save local JSON
    epoch_data = []
    for m in db.query(TrainMetric).filter(TrainMetric.task_id == task_id).order_by(TrainMetric.epoch).all():
        epoch_data.append({
            "epoch": m.epoch,
            "train_loss": float(m.train_loss) if m.train_loss else None,
            "val_loss": float(m.val_loss) if m.val_loss else None,
            "train_mae": float(m.train_mae) if m.train_mae else None,
            "val_mae": float(m.val_mae) if m.val_mae else None,
            "train_rmse": float(m.train_rmse) if m.train_rmse else None,
            "val_rmse": float(m.val_rmse) if m.val_rmse else None,
        })

    stock_dir = RESULT_DIR / ts_code.replace(".", "_")
    stock_dir.mkdir(parents=True, exist_ok=True)
    result_path = stock_dir / f"{model_type}_step{predict_steps}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump({
            "ts_code": ts_code, "model_type": model_type,
            "predict_steps": predict_steps, "epochs": EPOCHS,
            "best_val_loss": round(best_val_loss, 6),
            "epoch_metrics": epoch_data,
            "test_evaluation": metrics,
        }, f, ensure_ascii=False, indent=2)

    # Cleanup
    del model, train_loader, val_loader, test_loader
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return metrics


def main():
    print(f"\n{'='*60}")
    print(f"  逐股训练 | 每股 {EPOCHS} 轮 | 设备: {DEVICE}")
    print(f"  模型: {', '.join(MODELS)} | 步长: {PREDICT_STEPS}")
    print(f"{'='*60}\n")

    ensure_db_columns()

    db = SessionLocal()
    try:
        stocks = db.query(StockBasic).filter(StockBasic.list_status == "L").all()
        codes = [s.ts_code for s in stocks]
        total_stocks = len(codes)
        print(f"  共 {total_stocks} 只在市股票\n")

        completed_set = set()
        done_tasks = db.query(TrainTask).filter(TrainTask.status == "completed", TrainTask.current_epoch >= EPOCHS).all()
        for t in done_tasks:
            key = f"{t.ts_code}_{t.model_type}_{t.predict_steps}"
            ckpt_path = MODEL_DIR / f"{t.ts_code}_{t.model_type}_step{t.predict_steps}_checkpoint.pth"
            if not os.path.exists(str(ckpt_path)):
                completed_set.add(key)
        if completed_set:
            print(f"  已完成且无需续训的任务: {len(completed_set)} 个\n")

        summary = {"stocks": [], "started": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

        for si, ts_code in enumerate(codes):
            pct = (si + 1) / total_stocks * 100
            bar_len = 30
            filled = int(bar_len * (si + 1) / total_stocks)
            bar = "█" * filled + "░" * (bar_len - filled)
            print(f"\n  [{bar}] {pct:.1f}% ({si+1}/{total_stocks}) {ts_code}")
            stock_results = {"ts_code": ts_code, "tasks": []}

            for model_type in MODELS:
                for predict_steps in PREDICT_STEPS:
                    tag = f"{model_type}-step{predict_steps}"
                    skip_key = f"{ts_code}_{model_type}_{predict_steps}"
                    if skip_key in completed_set:
                        print(f"    {tag}: 已完成, 跳过")
                        stock_results["tasks"].append({"model": model_type, "steps": predict_steps, "status": "skipped_done"})
                        continue
                    try:
                        metrics = train_single_stock(db, ts_code, model_type, predict_steps)
                        if metrics:
                            mae = metrics.get("mae", 0)
                            r2 = metrics.get("r2", 0)
                            acc3 = metrics.get("accuracy_3pct", 0)
                            print(f"    {tag}: MAE={mae:.4f} R²={r2:.4f} 3%准确率={acc3:.1f}%")
                            stock_results["tasks"].append({
                                "model": model_type, "steps": predict_steps,
                                "status": "completed", "mae": mae, "r2": r2,
                            })
                        else:
                            print(f"    {tag}: 跳过(数据不足)")
                            stock_results["tasks"].append({
                                "model": model_type, "steps": predict_steps,
                                "status": "skipped",
                            })
                    except Exception as e:
                        print(f"    {tag}: 失败 - {str(e)[:100]}")
                        try:
                            db.rollback()
                        except Exception:
                            pass
                        stock_results["tasks"].append({
                            "model": model_type, "steps": predict_steps,
                            "status": "failed", "error": str(e)[:200],
                        })

            summary["stocks"].append(stock_results)

            if (si + 1) % 50 == 0:
                with open(RESULT_DIR / "progress.json", "w", encoding="utf-8") as f:
                    json.dump({
                        "completed": si + 1, "total": total_stocks,
                        "percent": round((si + 1) / total_stocks * 100, 1),
                    }, f)

        summary["finished"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary["total_stocks"] = total_stocks
        with open(RESULT_DIR / "all_stocks_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"\n{'='*60}")
        print(f"  全部训练完成! 共 {total_stocks} 只股票")
        print(f"  结果目录: {RESULT_DIR}")
        print(f"{'='*60}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
