"""
将 paper_output 的训练结果导入数据库，供前端页面展示
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
RESULT_DIR = BASE_DIR / "paper_output" / "results"
MODEL_DIR = BASE_DIR / "paper_output" / "models"

sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))

from app.database import SessionLocal
from app.models.db_models import TrainTask, TrainMetric, EvaluateResult, ModelFile

MODELS = ["BiLSTM", "Transformer", "TFT"]
STEPS = [1, 3, 5]


def import_all():
    db = SessionLocal()
    try:
        count = 0
        for model_type in MODELS:
            for step in STEPS:
                result_file = RESULT_DIR / f"{model_type}_step{step}.json"
                if not result_file.exists():
                    print(f"  跳过: {result_file.name} (不存在)")
                    continue

                with open(result_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                ts_code = data["ts_code"]
                tag = f"{model_type}-{ts_code}-step{step}"

                existing = db.query(TrainTask).filter(
                    TrainTask.model_type == model_type,
                    TrainTask.ts_code == ts_code,
                    TrainTask.predict_steps == step,
                    TrainTask.epochs == data["epochs_max"],
                    TrainTask.task_name.like("%论文%"),
                ).first()
                if existing:
                    print(f"  跳过: {tag} (已存在 task_id={existing.id})")
                    continue

                task = TrainTask(
                    task_name=f"论文训练-{tag}",
                    model_type=model_type,
                    ts_code=ts_code,
                    predict_steps=step,
                    lookback_window=30,
                    epochs=data["epochs_max"],
                    batch_size=32,
                    learning_rate=0.001,
                    val_ratio=0.15,
                    test_ratio=0.15,
                    status="completed",
                    current_epoch=data["epochs_run"],
                    best_val_loss=data["best_val_loss"],
                    model_path=str(MODEL_DIR / f"{ts_code}_{model_type}_step{step}_best.pth"),
                    started_at=datetime.now(),
                    finished_at=datetime.now(),
                )
                db.add(task)
                db.commit()
                db.refresh(task)
                task_id = task.id

                for em in data.get("epoch_metrics", []):
                    db.add(TrainMetric(
                        task_id=task_id,
                        epoch=em["epoch"],
                        train_loss=em.get("train_loss"),
                        val_loss=em.get("val_loss"),
                        train_mae=em.get("train_mae"),
                        val_mae=em.get("val_mae"),
                        train_rmse=em.get("train_rmse"),
                        val_rmse=em.get("val_rmse"),
                        learning_rate=em.get("learning_rate"),
                    ))

                te = data.get("test_evaluation", {})
                actual_prices = data.get("actual_prices", [])
                predicted_prices = data.get("predicted_prices", [])

                db.add(EvaluateResult(
                    train_task_id=task_id,
                    model_type=model_type,
                    ts_code=ts_code,
                    predict_steps=step,
                    dataset_type="test",
                    mae=te.get("price_mae"),
                    mse=te.get("price_mse"),
                    rmse=te.get("price_rmse"),
                    mape=te.get("price_mape"),
                    smape=te.get("price_smape"),
                    r2=te.get("price_r2"),
                    direction_accuracy=te.get("price_direction_accuracy"),
                    max_error=te.get("price_max_error"),
                    median_ae=te.get("price_median_ae"),
                    explained_variance=te.get("price_explained_variance"),
                    pearson_corr=te.get("price_pearson_corr"),
                    accuracy_1pct=te.get("price_accuracy_1pct"),
                    accuracy_3pct=te.get("price_accuracy_3pct"),
                    accuracy_5pct=te.get("price_accuracy_5pct"),
                    win_rate=te.get("price_win_rate"),
                    profit_factor=te.get("price_profit_factor"),
                    sharpe_ratio=te.get("price_sharpe_ratio"),
                    max_drawdown=te.get("price_max_drawdown"),
                    actual_values=json.dumps(actual_prices),
                    predicted_values=json.dumps(predicted_prices),
                ))

                model_path = MODEL_DIR / f"{ts_code}_{model_type}_step{step}_best.pth"
                file_size = model_path.stat().st_size if model_path.exists() else 0
                scaler_prefix = f"{ts_code}_{model_type}_step{step}"
                db.add(ModelFile(
                    train_task_id=task_id,
                    model_type=model_type,
                    ts_code=ts_code,
                    predict_steps=step,
                    file_path=str(model_path),
                    scaler_path=json.dumps({
                        "feature": str(MODEL_DIR / f"{scaler_prefix}_feature_scaler.pkl"),
                        "target": str(MODEL_DIR / f"{scaler_prefix}_target_scaler.pkl"),
                    }),
                    metrics=json.dumps({k: v for k, v in te.items() if k.startswith("price_")}),
                    is_best=1,
                    file_size=file_size,
                ))

                db.commit()
                count += 1
                print(f"  导入: {tag} → task_id={task_id} ({data['epochs_run']}轮)")

        print(f"\n完成! 共导入 {count} 条训练记录")

    finally:
        db.close()


if __name__ == "__main__":
    print("导入论文训练结果到数据库...\n")
    import_all()
