"""
智能高效训练脚本 — 少量数据 + 高质量训练 = 通用股票预测模型

核心优化:
  1. 智能分层抽样: 按行业等间距采样 ~400 只代表性股票 (减少 80-90% 数据)
  2. 互信息特征精选: 替代盲 PCA, 选出最具预测力的 top-K 特征
  3. 时序数据增强: 随机缩放 + 高斯噪声, 增强泛化能力
  4. 高效训练: 混合精度 + OneCycleLR + 早停, 50轮即可收敛
  5. 无股票嵌入: 模型完全基于技术指标模式, 可泛化到任意未见过的股票

产出: 3模型 × 3步长 = 9个模型 (与 universal 模型兼容)
"""
import sys
import os
import json
import gc
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from pathlib import Path
from datetime import datetime
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
RESULT_DIR = BASE_DIR / "smart_results"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))

from app.config import MODEL_DIR
from app.database import SessionLocal
from app.models.db_models import StockBasic, TrainTask, TrainMetric, EvaluateResult, ModelFile
from app.services.feature_engineer import compute_features
from app.services.trainer import _build_model
from app.services.evaluator import compute_metrics
from app.utils.logger import get_logger
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import mutual_info_regression
import joblib

logger = get_logger("smart_train")
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
USE_AMP = DEVICE.type == "cuda"

def _autocast():
    """兼容不同 PyTorch 版本的 AMP autocast"""
    try:
        return torch.amp.autocast(DEVICE.type, enabled=USE_AMP)
    except TypeError:
        return torch.cuda.amp.autocast(enabled=USE_AMP)

def _grad_scaler():
    """兼容不同 PyTorch 版本的 GradScaler"""
    try:
        return torch.amp.GradScaler(DEVICE.type, enabled=USE_AMP)
    except TypeError:
        return torch.cuda.amp.GradScaler(enabled=USE_AMP)

# ── 超参数 ──────────────────────────────────────────────────
EPOCHS = 50
BATCH_SIZE = 256
LEARNING_RATE = 0.003
LOOKBACK = 30
TARGET_STOCK_COUNT = 400
TOP_K_FEATURES = 25
MODELS = ["BiLSTM", "Transformer", "TFT"]
PREDICT_STEPS_LIST = [1, 3, 5]
EARLY_STOP_PATIENCE = 0  # 0 = 禁用早停, 跑满全部 EPOCHS 轮
AUG_SCALE_SIGMA = 0.05
AUG_NOISE_SIGMA = 0.01


# ═══════════════════════════════════════════════════════════
# 1. 智能分层抽样
# ═══════════════════════════════════════════════════════════

def smart_sample_stocks(db, target_count=TARGET_STOCK_COUNT):
    """按行业分层等间距抽样, 保证全行业覆盖"""
    stocks = (
        db.query(StockBasic)
        .filter(StockBasic.list_status == "L")
        .order_by(StockBasic.ts_code)
        .all()
    )

    industry_groups = defaultdict(list)
    for s in stocks:
        industry_groups[s.industry or "未知"].append(s)

    num_industries = len(industry_groups)
    per_industry = max(3, target_count // num_industries)

    sampled = []
    for industry, group in sorted(industry_groups.items()):
        step = max(1, len(group) // per_industry)
        picked = group[::step][:per_industry]
        sampled.extend(picked)

    if len(sampled) > target_count:
        step = max(1, len(sampled) // target_count)
        sampled = sampled[::step][:target_count]

    codes = [s.ts_code for s in sampled]
    print(f"  智能抽样: {len(stocks)} 只 → {len(codes)} 只 "
          f"(覆盖 {num_industries} 个行业, 每行业 ~{per_industry} 只)")
    return codes


# ═══════════════════════════════════════════════════════════
# 2. 互信息特征精选
# ═══════════════════════════════════════════════════════════

def select_features_by_mutual_info(stock_dfs, top_k=TOP_K_FEATURES):
    """用互信息 + 去冗余选出最具预测力的 top-K 特征"""
    sample_codes = list(stock_dfs.keys())
    if len(sample_codes) > 50:
        np.random.seed(42)
        sample_codes = list(np.random.choice(sample_codes, 50, replace=False))

    all_X, all_y = [], []
    for code in sample_codes:
        df = stock_dfs[code]
        fdf = df.drop(columns=["trade_date"], errors="ignore")
        cols = fdf.columns.tolist()
        if "close" not in cols:
            continue
        close_idx = cols.index("close")
        vals = fdf.values.astype(np.float64)
        close = vals[:, close_idx]
        ret_1d = np.diff(close) / (close[:-1] + 1e-8)
        all_X.append(vals[:-1])
        all_y.append(ret_1d)

    X = np.concatenate(all_X, axis=0)
    y = np.concatenate(all_y, axis=0)

    valid_mask = np.isfinite(X).all(axis=1) & np.isfinite(y)
    X, y = X[valid_mask], y[valid_mask]

    if len(X) > 100000:
        idx = np.random.choice(len(X), 100000, replace=False)
        X, y = X[idx], y[idx]

    feature_names = list(stock_dfs[list(stock_dfs.keys())[0]]
                         .drop(columns=["trade_date"], errors="ignore").columns)

    print(f"  计算互信息 ({len(feature_names)} 个特征, {len(X)} 条样本)...")
    mi_scores = mutual_info_regression(X, y, random_state=42, n_neighbors=5)

    corr_matrix = np.corrcoef(X.T)
    corr_matrix = np.nan_to_num(corr_matrix, nan=0.0)
    ranked_indices = np.argsort(mi_scores)[::-1]

    selected = []
    for idx in ranked_indices:
        if len(selected) >= top_k:
            break
        redundant = False
        for s in selected:
            if abs(corr_matrix[idx, s]) > 0.95:
                redundant = True
                break
        if not redundant:
            selected.append(idx)

    selected = sorted(selected)
    selected_names = [feature_names[i] for i in selected]

    if "close" not in selected_names:
        close_idx = feature_names.index("close")
        if close_idx not in selected:
            selected.append(close_idx)
            selected = sorted(selected)
            selected_names = [feature_names[i] for i in selected]

    print(f"  精选特征: {len(feature_names)} → {len(selected_names)} 个")
    top5 = [(feature_names[i], round(mi_scores[i], 4))
            for i in np.argsort(mi_scores)[::-1][:5]]
    print(f"  互信息 Top5: {top5}")

    return selected_names


# ═══════════════════════════════════════════════════════════
# 3. 时序数据增强 Dataset
# ═══════════════════════════════════════════════════════════

class AugmentedDataset(Dataset):
    """训练时在线数据增强: 随机缩放 + 高斯噪声"""

    def __init__(self, X, y, augment=True):
        self.X = X
        self.y = y
        self.augment = augment

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        x = torch.from_numpy(np.array(self.X[idx], dtype=np.float32))
        y = torch.from_numpy(np.array(self.y[idx], dtype=np.float32))

        if self.augment:
            scale = torch.normal(1.0, AUG_SCALE_SIGMA, size=(1, 1))
            x = x * scale
            noise = torch.normal(0.0, AUG_NOISE_SIGMA, size=x.shape)
            x = x + noise

        return x, y


# ═══════════════════════════════════════════════════════════
# 4. 数据准备 (无 PCA, 无股票嵌入)
# ═══════════════════════════════════════════════════════════

class SmartDataProcessor:
    """精简数据处理器: 特征精选 + 标准化, 无 PCA/无股票嵌入"""

    def __init__(self, lookback=LOOKBACK, predict_steps=1,
                 val_ratio=0.15, test_ratio=0.15):
        self.lookback = lookback
        self.predict_steps = predict_steps
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.feature_scaler = StandardScaler()
        self.target_scaler = StandardScaler()
        self.feature_columns = []
        self.test_base_prices = None

    def prepare(self, stock_dfs, selected_features):
        self.feature_columns = selected_features
        close_col = "close"
        if close_col not in selected_features:
            raise ValueError("selected_features 必须包含 close")
        close_idx = selected_features.index(close_col)

        stock_meta = []
        for ts_code, df in stock_dfs.items():
            fdf = df[selected_features].astype(np.float32)
            vals = fdf.values
            close_prices = vals[:, close_idx].copy()
            n = len(vals)
            test_size = int(n * self.test_ratio)
            val_size = int(n * self.val_ratio)
            train_size = n - val_size - test_size
            if train_size < self.lookback + self.predict_steps + 5:
                continue
            stock_meta.append({
                "features": vals,
                "close_prices": close_prices,
                "train_size": train_size,
                "val_size": val_size,
                "test_size": test_size,
                "n": n,
            })

        train_portions = [m["features"][:m["train_size"]] for m in stock_meta]
        combined_train = np.concatenate(train_portions, axis=0)
        self.feature_scaler.fit(combined_train)
        del combined_train, train_portions

        train_Xs, train_ys = [], []
        val_Xs, val_ys = [], []
        test_Xs, test_ys = [], []
        test_bps = []
        all_train_returns = []

        for m in stock_meta:
            scaled = self.feature_scaler.transform(m["features"]).astype(np.float32)
            X, y, bp = self._create_return_sequences(scaled, m["close_prices"])
            if len(X) == 0:
                continue

            te = max(1, m["train_size"] - self.lookback - self.predict_steps + 1)
            ve = max(te + 1, m["train_size"] + m["val_size"]
                     - self.lookback - self.predict_steps + 1)

            train_Xs.append(X[:te])
            train_ys.append(y[:te])
            all_train_returns.append(y[:te])
            if ve > te:
                val_Xs.append(X[te:ve])
                val_ys.append(y[te:ve])
            if len(X) > ve:
                test_Xs.append(X[ve:])
                test_ys.append(y[ve:])
                test_bps.append(bp[ve:])

        if not train_Xs:
            raise ValueError("无有效训练数据")

        train_X = np.concatenate(train_Xs)
        train_y = np.concatenate(train_ys)

        shuffle_idx = np.random.permutation(len(train_X))
        train_X = train_X[shuffle_idx]
        train_y = train_y[shuffle_idx]

        feat_dim = train_X.shape[2]
        val_X = np.concatenate(val_Xs) if val_Xs else np.empty(
            (0, self.lookback, feat_dim), dtype=np.float32)
        val_y = np.concatenate(val_ys) if val_ys else np.empty(
            (0, self.predict_steps), dtype=np.float32)
        test_X = np.concatenate(test_Xs) if test_Xs else np.empty(
            (0, self.lookback, feat_dim), dtype=np.float32)
        test_y = np.concatenate(test_ys) if test_ys else np.empty(
            (0, self.predict_steps), dtype=np.float32)
        self.test_base_prices = (np.concatenate(test_bps)
                                 if test_bps else np.array([]))

        combined_returns = np.concatenate(all_train_returns)
        self.target_scaler.fit(combined_returns)
        train_y = self.target_scaler.transform(train_y).astype(np.float32)
        if len(val_y) > 0:
            val_y = self.target_scaler.transform(val_y).astype(np.float32)
        if len(test_y) > 0:
            test_y = self.target_scaler.transform(test_y).astype(np.float32)

        print(f"  数据: 训练={len(train_X)} 验证={len(val_X)} "
              f"测试={len(test_X)} 特征={feat_dim}")
        return train_X, train_y, val_X, val_y, test_X, test_y

    def _create_return_sequences(self, features, close_prices):
        X, y, bp = [], [], []
        max_i = len(features) - self.lookback - self.predict_steps + 1
        for i in range(max_i):
            X.append(features[i: i + self.lookback])
            base = close_prices[i + self.lookback - 1]
            returns = [(close_prices[i + self.lookback + j] - base)
                       / (base + 1e-8)
                       for j in range(self.predict_steps)]
            y.append(returns)
            bp.append(base)
        return (np.array(X, dtype=np.float32),
                np.array(y, dtype=np.float32),
                np.array(bp, dtype=np.float32))

    def inverse_transform_target(self, scaled_values, base_prices=None):
        bp = base_prices if base_prices is not None else self.test_base_prices
        if scaled_values.ndim == 1:
            scaled_values = scaled_values.reshape(-1, self.predict_steps)
        returns = self.target_scaler.inverse_transform(scaled_values)
        if bp is not None and len(bp) > 0:
            prices = bp.reshape(-1, 1) * (1 + returns)
            return prices.flatten()
        return returns.flatten()


# ═══════════════════════════════════════════════════════════
# 5. 高效训练循环
# ═══════════════════════════════════════════════════════════

def train_smart_model(stock_dfs, selected_features, model_type,
                      predict_steps, db):
    tag = f"{model_type}_step{predict_steps}"
    print(f"\n{'─'*55}")
    print(f"  智能训练: {model_type} | 步长={predict_steps}天 | "
          f"股票={len(stock_dfs)}只 | 特征={len(selected_features)}个")
    print(f"{'─'*55}")

    processor = SmartDataProcessor(
        lookback=LOOKBACK, predict_steps=predict_steps,
        val_ratio=0.15, test_ratio=0.15,
    )
    train_X, train_y, val_X, val_y, test_X, test_y = processor.prepare(
        stock_dfs, selected_features
    )

    input_size = train_X.shape[2]
    model = _build_model(model_type, input_size, predict_steps)
    model = model.to(DEVICE)
    param_count = sum(p.numel() for p in model.parameters())
    print(f"  参数量: {param_count:,}")

    train_loader = DataLoader(
        AugmentedDataset(train_X, train_y, augment=True),
        batch_size=BATCH_SIZE, shuffle=True,
        num_workers=0, pin_memory=True,
    )
    val_loader = DataLoader(
        AugmentedDataset(val_X, val_y, augment=False),
        batch_size=BATCH_SIZE, shuffle=False,
        num_workers=0, pin_memory=True,
    )

    criterion = nn.SmoothL1Loss()
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4
    )
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=LEARNING_RATE,
        epochs=EPOCHS, steps_per_epoch=len(train_loader),
        pct_start=0.2, anneal_strategy="cos",
    )

    amp_scaler = _grad_scaler()
    model_path = str(
        MODEL_DIR / f"smart_{model_type}_step{predict_steps}_best.pth"
    )
    best_val_loss = float("inf")
    patience_counter = 0
    epoch_metrics = []

    for epoch in range(1, EPOCHS + 1):
        # ── 训练 ──
        model.train()
        tl, tm, tms, tc = 0, 0, 0, 0
        for xb, yb in train_loader:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            with _autocast():
                out = model(xb)
                loss = criterion(out, yb)
            amp_scaler.scale(loss).backward()
            amp_scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            amp_scaler.step(optimizer)
            amp_scaler.update()
            scheduler.step()

            bn = len(xb)
            tl += loss.item() * bn
            with torch.no_grad():
                tm += torch.mean(torch.abs(out - yb)).item() * bn
                tms += torch.mean((out - yb) ** 2).item() * bn
            tc += bn

        train_loss = tl / max(tc, 1)
        train_mae = tm / max(tc, 1)
        train_rmse = (tms / max(tc, 1)) ** 0.5

        if np.isnan(train_loss):
            continue

        # ── 验证 ──
        model.eval()
        vl, vm, vms, vc = 0, 0, 0, 0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(DEVICE), yb.to(DEVICE)
                with _autocast():
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
            patience_counter = 0
            torch.save(model.state_dict(), model_path)
        else:
            patience_counter += 1

        if epoch % 5 == 0 or epoch == 1 or epoch == EPOCHS:
            print(f"  Epoch {epoch:>3}/{EPOCHS} | TL={train_loss:.5f} "
                  f"VL={val_loss:.5f} | V_MAE={val_mae:.5f} | "
                  f"Best={best_val_loss:.5f} | P={patience_counter} | "
                  f"LR={current_lr:.2e}")

        if EARLY_STOP_PATIENCE > 0 and patience_counter >= EARLY_STOP_PATIENCE:
            print(f"  早停触发: 连续 {EARLY_STOP_PATIENCE} 轮未改善, "
                  f"停在 Epoch {epoch}")
            break

    if not os.path.exists(model_path):
        print(f"  ✗ {tag} 未产生有效模型")
        return None

    # ── 测试评估 ──
    model.load_state_dict(
        torch.load(model_path, map_location=DEVICE, weights_only=True)
    )
    model.eval()

    all_preds, all_actuals = [], []
    test_loader = DataLoader(
        AugmentedDataset(test_X, test_y, augment=False),
        batch_size=BATCH_SIZE, shuffle=False,
    )
    with torch.no_grad():
        for xb, yb in test_loader:
            xb = xb.to(DEVICE)
            with _autocast():
                all_preds.append(model(xb).cpu().float().numpy())
            all_actuals.append(yb.numpy())

    preds = np.concatenate(all_preds, axis=0).flatten()
    actuals = np.concatenate(all_actuals, axis=0).flatten()
    pred_prices = processor.inverse_transform_target(preds)
    actual_prices = processor.inverse_transform_target(actuals)
    metrics = compute_metrics(actual_prices, pred_prices)

    # ── 保存 scaler ──
    prefix = f"smart_{model_type}_step{predict_steps}"
    joblib.dump(processor.feature_scaler,
                str(MODEL_DIR / f"{prefix}_feature_scaler.pkl"))
    joblib.dump(processor.target_scaler,
                str(MODEL_DIR / f"{prefix}_target_scaler.pkl"))
    with open(str(MODEL_DIR / f"{prefix}_selected_features.json"), "w") as f:
        json.dump(selected_features, f, ensure_ascii=False)

    # ── 写入数据库 ──
    task = TrainTask(
        task_name=f"智能模型-{model_type}-step{predict_steps}",
        model_type=model_type, ts_code="smart_universal",
        predict_steps=predict_steps, lookback_window=LOOKBACK,
        epochs=EPOCHS, batch_size=BATCH_SIZE,
        learning_rate=LEARNING_RATE,
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
        ts_code="smart_universal", predict_steps=predict_steps,
        dataset_type="test",
        mae=metrics.get("mae"), mse=metrics.get("mse"),
        rmse=metrics.get("rmse"), mape=metrics.get("mape"),
        smape=metrics.get("smape"), r2=metrics.get("r2"),
        direction_accuracy=metrics.get("direction_accuracy"),
        max_error=metrics.get("max_error"),
        median_ae=metrics.get("median_ae"),
        explained_variance=metrics.get("explained_variance"),
        pearson_corr=metrics.get("pearson_corr"),
        accuracy_1pct=metrics.get("accuracy_1pct"),
        accuracy_3pct=metrics.get("accuracy_3pct"),
        accuracy_5pct=metrics.get("accuracy_5pct"),
        win_rate=metrics.get("win_rate"),
        profit_factor=metrics.get("profit_factor"),
        sharpe_ratio=metrics.get("sharpe_ratio"),
        max_drawdown=metrics.get("max_drawdown"),
        actual_values=json.dumps(actual_prices[:500].tolist()),
        predicted_values=json.dumps(pred_prices[:500].tolist()),
    ))

    file_size = (os.path.getsize(model_path)
                 if os.path.exists(model_path) else 0)
    db.add(ModelFile(
        train_task_id=task_id, model_type=model_type,
        ts_code="smart_universal", predict_steps=predict_steps,
        file_path=model_path,
        scaler_path=json.dumps({
            "feature": str(MODEL_DIR / f"{prefix}_feature_scaler.pkl"),
            "target": str(MODEL_DIR / f"{prefix}_target_scaler.pkl"),
        }),
        feature_config=json.dumps(selected_features),
        metrics=json.dumps(metrics),
        is_best=1, file_size=file_size,
    ))
    db.commit()

    with open(RESULT_DIR / f"{tag}.json", "w", encoding="utf-8") as f:
        json.dump({
            "model_type": model_type, "predict_steps": predict_steps,
            "num_stocks": len(stock_dfs),
            "selected_features": selected_features,
            "epochs_trained": len(epoch_metrics),
            "best_val_loss": round(best_val_loss, 6),
            "param_count": param_count,
            "train_samples": len(train_X),
            "val_samples": len(val_X),
            "test_samples": len(test_X),
            "epoch_metrics": epoch_metrics,
            "test_evaluation": metrics,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n  ✓ {model_type} step{predict_steps} 完成 "
          f"(task_id={task_id}, {len(epoch_metrics)}轮):")
    print(f"    MAE={metrics['mae']:.4f} | RMSE={metrics['rmse']:.4f} | "
          f"MAPE={metrics['mape']:.2f}% | R²={metrics['r2']:.4f}")
    print(f"    模型: {model_path} ({file_size/1024/1024:.1f}MB)")

    del model, train_loader, val_loader, test_loader
    del train_X, train_y, val_X, val_y, test_X, test_y
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return metrics


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════

def main():
    start_time = datetime.now()

    print(f"\n{'='*60}")
    print(f"  智能高效训练 | {EPOCHS}轮(+早停) | 设备: {DEVICE}")
    print(f"  模型: {', '.join(MODELS)}")
    print(f"  步长: {PREDICT_STEPS_LIST}")
    print(f"  目标股票数: ~{TARGET_STOCK_COUNT}")
    print(f"  特征数: top {TOP_K_FEATURES} (互信息精选)")
    print(f"  数据增强: 缩放σ={AUG_SCALE_SIGMA} 噪声σ={AUG_NOISE_SIGMA}")
    print(f"  混合精度: {'开启' if USE_AMP else '关闭 (CPU模式)'}")
    print(f"{'='*60}")

    db = SessionLocal()
    try:
        # Step 1: 智能抽样
        print(f"\n▸ Step 1/4: 智能分层抽样")
        codes = smart_sample_stocks(db, TARGET_STOCK_COUNT)

        # Step 2: 加载特征数据
        print(f"\n▸ Step 2/4: 加载特征数据")
        stock_dfs = {}
        skipped = 0
        for i, ts_code in enumerate(codes):
            if (i + 1) % 50 == 0 or (i + 1) == len(codes):
                print(f"    进度: {i+1}/{len(codes)} "
                      f"({(i+1)/len(codes)*100:.0f}%)")
            try:
                df = compute_features(db, ts_code, save_to_db=False)
                if df.empty or len(df) < LOOKBACK + 5 + 20:
                    skipped += 1
                    continue
                stock_dfs[ts_code] = df
            except Exception:
                skipped += 1
                continue
        print(f"  有效股票: {len(stock_dfs)} 只, 跳过: {skipped} 只")

        if not stock_dfs:
            print("  无有效数据, 请先运行数据采集")
            return

        # Step 3: 互信息特征精选
        print(f"\n▸ Step 3/4: 互信息特征精选")
        selected_features = select_features_by_mutual_info(
            stock_dfs, TOP_K_FEATURES
        )

        # Step 4: 训练
        print(f"\n▸ Step 4/4: 模型训练")
        all_metrics = {}
        task_idx = 0
        total_tasks = len(MODELS) * len(PREDICT_STEPS_LIST)

        for predict_steps in PREDICT_STEPS_LIST:
            all_metrics[predict_steps] = {}
            for model_type in MODELS:
                task_idx += 1
                print(f"\n  ===== 任务 {task_idx}/{total_tasks} =====")
                try:
                    metrics = train_smart_model(
                        stock_dfs, selected_features,
                        model_type, predict_steps, db,
                    )
                    if metrics:
                        all_metrics[predict_steps][model_type] = metrics
                except Exception as e:
                    print(f"  ✗ {model_type} step{predict_steps} "
                          f"失败: {str(e)[:200]}")
                    import traceback
                    traceback.print_exc()
                    try:
                        db.rollback()
                    except Exception:
                        pass

        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n{'='*60}")
        print(f"  智能训练全部完成!")
        print(f"  耗时: {elapsed/60:.1f}分钟 ({elapsed:.0f}秒)")
        print(f"{'='*60}")

        for predict_steps in PREDICT_STEPS_LIST:
            step_m = all_metrics.get(predict_steps, {})
            if not step_m:
                continue
            print(f"\n  {predict_steps}天步长对比:")
            print(f"  {'模型':<14} {'MAE':>8} {'RMSE':>8} "
                  f"{'MAPE%':>8} {'R²':>8}")
            for m in MODELS:
                if m in step_m:
                    v = step_m[m]
                    print(f"  {m:<14} {v['mae']:>8.4f} "
                          f"{v['rmse']:>8.4f} {v['mape']:>8.2f} "
                          f"{v['r2']:>8.4f}")

        model_files = list(MODEL_DIR.glob("smart_*"))
        total_size = sum(f.stat().st_size for f in model_files) / 1024 / 1024
        print(f"\n  智能模型文件: {len(model_files)} 个, "
              f"总计 {total_size:.1f}MB")

    finally:
        db.close()


if __name__ == "__main__":
    main()
