"""
通用模型训练脚本 — 全A股数据合并训练 BiLSTM/Transformer/TFT
最终产出：3模型 × 3步长 = 9个模型文件（约50MB），替代30G+的单股票模型
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
RESULT_DIR = BASE_DIR / "universal_results"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))

from app.config import MODEL_DIR
from app.database import SessionLocal
from app.models.db_models import StockBasic, TrainTask, TrainMetric, EvaluateResult, ModelFile
from app.services.feature_engineer import compute_features
from app.core.data_processor import TimeSeriesProcessor
from app.services.trainer import _build_model
from app.services.evaluator import compute_metrics
from app.utils.logger import get_logger
import joblib

logger = get_logger("universal_train")
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

EPOCHS = 100
BATCH_SIZE = 128
LEARNING_RATE = 0.001
LOOKBACK = 30
CHUNK_SIZE = 500
MODELS = ["BiLSTM", "Transformer", "TFT"]
PREDICT_STEPS_LIST = [1, 3, 5]


class MemmapDataset(torch.utils.data.Dataset):
    """支持 memmap 的 Dataset，避免一次性加载全部数据到内存"""
    def __init__(self, X, y):
        self.X = X
        self.y = y

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return torch.from_numpy(np.array(self.X[idx])), torch.from_numpy(np.array(self.y[idx]))


def load_all_stock_features(db, max_stocks=None):
    """分批加载股票特征数据。max_stocks=None 表示加载全部股票。"""
    stocks = db.query(StockBasic).filter(StockBasic.list_status == "L").order_by(StockBasic.ts_code).all()
    codes = [s.ts_code for s in stocks]
    if max_stocks:
        codes = codes[:max_stocks]

    print(f"  开始加载 {len(codes)} 只股票的特征数据...")
    stock_dfs = {}
    skipped = 0

    for i, ts_code in enumerate(codes):
        if (i + 1) % 100 == 0 or (i + 1) == len(codes):
            print(f"    加载进度: {i+1}/{len(codes)} ({(i+1)/len(codes)*100:.1f}%)")

        try:
            df = compute_features(db, ts_code, save_to_db=False)
            if df.empty or len(df) < LOOKBACK + 5 + 20:
                skipped += 1
                continue
            stock_dfs[ts_code] = df
        except Exception:
            skipped += 1
            continue

        if (i + 1) % CHUNK_SIZE == 0:
            gc.collect()

    print(f"  加载完成: {len(stock_dfs)} 只有效股票, 跳过 {skipped} 只")
    return stock_dfs


def train_universal_model(stock_dfs, model_type, predict_steps, db):
    tag = f"{model_type}_step{predict_steps}"
    print(f"\n{'─'*55}")
    print(f"  通用模型训练: {model_type} | 步长={predict_steps}天 | 股票={len(stock_dfs)}只")
    print(f"{'─'*55}")

    processor = TimeSeriesProcessor(
        lookback=LOOKBACK, predict_steps=predict_steps,
        pca_components=25, val_ratio=0.15, test_ratio=0.15,
    )

    use_chunked = len(stock_dfs) > CHUNK_SIZE
    if use_chunked:
        print(f"  股票数>{CHUNK_SIZE}, 使用分批处理模式 (memmap)")
        train_X, train_y, val_X, val_y, test_X, test_y = processor.prepare_multi_stock_data_chunked(
            stock_dfs, chunk_size=CHUNK_SIZE
        )
    else:
        train_X, train_y, val_X, val_y, test_X, test_y = processor.prepare_multi_stock_data(stock_dfs)
    print(f"  数据: 训练={len(train_X)} 验证={len(val_X)} 测试={len(test_X)} 特征={train_X.shape[2]}")

    input_size = train_X.shape[2]
    model = _build_model(model_type, input_size, predict_steps)
    model = model.to(DEVICE)
    param_count = sum(p.numel() for p in model.parameters())
    print(f"  参数量: {param_count:,}")

    if use_chunked:
        train_loader = DataLoader(
            MemmapDataset(train_X, train_y),
            batch_size=BATCH_SIZE, shuffle=True, num_workers=0, pin_memory=True,
        )
        val_loader = DataLoader(
            MemmapDataset(val_X, val_y),
            batch_size=BATCH_SIZE, shuffle=False, num_workers=0, pin_memory=True,
        )
    else:
        train_loader = DataLoader(
            TensorDataset(torch.from_numpy(train_X), torch.from_numpy(train_y)),
            batch_size=BATCH_SIZE, shuffle=True, num_workers=0, pin_memory=True,
        )
        val_loader = DataLoader(
            TensorDataset(torch.from_numpy(val_X), torch.from_numpy(val_y)),
            batch_size=BATCH_SIZE, shuffle=False, num_workers=0, pin_memory=True,
        )

    criterion = nn.SmoothL1Loss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(optimizer, T_0=10, T_mult=2, eta_min=1e-6)

    model_path = str(MODEL_DIR / f"universal_{model_type}_step{predict_steps}_best.pth")
    checkpoint_path = str(MODEL_DIR / f"universal_{model_type}_step{predict_steps}_checkpoint.pth")
    best_val_loss = float("inf")
    start_epoch = 1
    epoch_metrics = []

    if os.path.exists(checkpoint_path):
        ckpt = torch.load(checkpoint_path, map_location=DEVICE)
        model.load_state_dict(ckpt["model_state"])
        optimizer.load_state_dict(ckpt["optimizer_state"])
        scheduler.load_state_dict(ckpt["scheduler_state"])
        start_epoch = ckpt["epoch"] + 1
        best_val_loss = ckpt.get("best_val_loss", float("inf"))
        epoch_metrics = ckpt.get("epoch_metrics", [])
        print(f"  断点续训: 从Epoch {start_epoch}继续, Best={best_val_loss:.6f}")

    if start_epoch > EPOCHS:
        print(f"  已完成全部{EPOCHS}轮, 跳过训练")
    else:
        for epoch in range(start_epoch, EPOCHS + 1):
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

            torch.save({
                "epoch": epoch,
                "model_state": model.state_dict(),
                "optimizer_state": optimizer.state_dict(),
                "scheduler_state": scheduler.state_dict(),
                "best_val_loss": best_val_loss,
                "epoch_metrics": epoch_metrics,
            }, checkpoint_path)

            if epoch % 5 == 0 or epoch == 1 or epoch == EPOCHS:
                print(f"  Epoch {epoch:>3}/{EPOCHS} | TL={train_loss:.5f} VL={val_loss:.5f} | "
                      f"V_MAE={val_mae:.5f} | Best={best_val_loss:.5f} | LR={current_lr:.2e}")

    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)

    if not os.path.exists(model_path):
        print(f"  ✗ {tag} 未产生有效模型")
        return None

    model.load_state_dict(torch.load(model_path, map_location=DEVICE, weights_only=True))
    model.eval()

    all_preds, all_actuals = [], []
    if use_chunked:
        test_loader = DataLoader(
            MemmapDataset(test_X, test_y),
            batch_size=BATCH_SIZE, shuffle=False,
        )
    else:
        test_loader = DataLoader(
            TensorDataset(torch.from_numpy(test_X), torch.from_numpy(test_y)),
            batch_size=BATCH_SIZE, shuffle=False,
        )
    with torch.no_grad():
        for xb, yb in test_loader:
            xb = xb.to(DEVICE)
            all_preds.append(model(xb).cpu().numpy())
            all_actuals.append(yb.numpy())

    preds = np.concatenate(all_preds, axis=0).flatten()
    actuals = np.concatenate(all_actuals, axis=0).flatten()
    pred_prices = processor.inverse_transform_target(preds)
    actual_prices = processor.inverse_transform_target(actuals)
    metrics = compute_metrics(actual_prices, pred_prices)

    prefix = f"universal_{model_type}_step{predict_steps}"
    joblib.dump(processor.feature_scaler, str(MODEL_DIR / f"{prefix}_feature_scaler.pkl"))
    joblib.dump(processor.target_scaler, str(MODEL_DIR / f"{prefix}_target_scaler.pkl"))
    if processor.pca is not None:
        joblib.dump(processor.pca, str(MODEL_DIR / f"{prefix}_pca.pkl"))
    if processor.stock_id_map:
        with open(str(MODEL_DIR / f"{prefix}_stock_id_map.json"), "w") as f:
            json.dump(processor.stock_id_map, f)

    task = TrainTask(
        task_name=f"通用模型-{model_type}-step{predict_steps}",
        model_type=model_type, ts_code="universal",
        predict_steps=predict_steps, lookback_window=LOOKBACK,
        epochs=EPOCHS, batch_size=BATCH_SIZE, learning_rate=LEARNING_RATE,
        val_ratio=0.15, test_ratio=0.15, status="completed",
        current_epoch=len(epoch_metrics),
        best_val_loss=round(best_val_loss, 6),
        model_path=model_path,
        started_at=datetime.now(), finished_at=datetime.now(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    task_id = task.id

    for em in epoch_metrics:
        db.add(TrainMetric(
            task_id=task_id, epoch=em["epoch"],
            train_loss=em["train_loss"], val_loss=em["val_loss"],
            train_mae=em["train_mae"], val_mae=em["val_mae"],
            train_rmse=em["train_rmse"], val_rmse=em["val_rmse"],
            learning_rate=em["learning_rate"],
        ))

    db.add(EvaluateResult(
        train_task_id=task_id, model_type=model_type,
        ts_code="universal", predict_steps=predict_steps, dataset_type="test",
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
        actual_values=json.dumps(actual_prices[:500].tolist()),
        predicted_values=json.dumps(pred_prices[:500].tolist()),
    ))

    file_size = os.path.getsize(model_path) if os.path.exists(model_path) else 0
    db.add(ModelFile(
        train_task_id=task_id, model_type=model_type,
        ts_code="universal", predict_steps=predict_steps,
        file_path=model_path,
        scaler_path=json.dumps({
            "feature": str(MODEL_DIR / f"{prefix}_feature_scaler.pkl"),
            "target": str(MODEL_DIR / f"{prefix}_target_scaler.pkl"),
        }),
        feature_config=json.dumps(processor.feature_columns),
        metrics=json.dumps(metrics),
        is_best=1, file_size=file_size,
    ))
    db.commit()

    with open(RESULT_DIR / f"{tag}.json", "w", encoding="utf-8") as f:
        json.dump({
            "model_type": model_type, "predict_steps": predict_steps,
            "num_stocks": len(stock_dfs), "epochs": EPOCHS,
            "best_val_loss": round(best_val_loss, 6),
            "param_count": param_count,
            "train_samples": len(train_X), "val_samples": len(val_X), "test_samples": len(test_X),
            "epoch_metrics": epoch_metrics, "test_evaluation": metrics,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n  ✓ {model_type} step{predict_steps} 完成 (task_id={task_id}):")
    print(f"    MAE={metrics['mae']:.4f} | RMSE={metrics['rmse']:.4f} | "
          f"MAPE={metrics['mape']:.2f}% | R²={metrics['r2']:.4f}")
    print(f"    模型: {model_path} ({file_size/1024/1024:.1f}MB)")

    del model, train_loader, val_loader, test_loader, train_X, train_y, val_X, val_y, test_X, test_y
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    processor.cleanup_temp_memmap()

    return metrics


def main():
    start_time = datetime.now()

    print(f"\n{'='*60}")
    print(f"  通用模型训练 | {EPOCHS}轮 | 设备: {DEVICE}")
    print(f"  模型: {', '.join(MODELS)}")
    print(f"  步长: {PREDICT_STEPS_LIST}")
    print(f"  总任务: {len(MODELS)} × {len(PREDICT_STEPS_LIST)} = {len(MODELS)*len(PREDICT_STEPS_LIST)} 个")
    print(f"{'='*60}")

    db = SessionLocal()
    try:
        stock_dfs = load_all_stock_features(db)
        if not stock_dfs:
            print("  无有效股票数据，请先运行数据采集")
            return

        all_metrics = {}
        task_idx = 0
        total_tasks = len(MODELS) * len(PREDICT_STEPS_LIST)

        for predict_steps in PREDICT_STEPS_LIST:
            all_metrics[predict_steps] = {}
            for model_type in MODELS:
                task_idx += 1
                print(f"\n  ===== 任务 {task_idx}/{total_tasks} =====")
                try:
                    metrics = train_universal_model(stock_dfs, model_type, predict_steps, db)
                    if metrics:
                        all_metrics[predict_steps][model_type] = metrics
                except Exception as e:
                    print(f"  ✗ {model_type} step{predict_steps} 失败: {str(e)[:200]}")
                    try:
                        db.rollback()
                    except Exception:
                        pass

        print(f"\n{'='*60}")
        print(f"  通用模型训练全部完成!")
        print(f"  耗时: {(datetime.now() - start_time).total_seconds()/60:.1f}分钟")
        print(f"{'='*60}")

        for predict_steps in PREDICT_STEPS_LIST:
            step_m = all_metrics.get(predict_steps, {})
            if not step_m:
                continue
            print(f"\n  {predict_steps}天步长对比:")
            print(f"  {'模型':<14} {'MAE':>8} {'RMSE':>8} {'MAPE%':>8} {'R²':>8}")
            for m in MODELS:
                if m in step_m:
                    v = step_m[m]
                    print(f"  {m:<14} {v['mae']:>8.4f} {v['rmse']:>8.4f} {v['mape']:>8.2f} {v['r2']:>8.4f}")

        model_files = list(MODEL_DIR.glob("universal_*"))
        total_size = sum(f.stat().st_size for f in model_files) / 1024 / 1024
        print(f"\n  通用模型文件: {len(model_files)} 个, 总计 {total_size:.1f}MB")

    finally:
        db.close()


if __name__ == "__main__":
    main()
