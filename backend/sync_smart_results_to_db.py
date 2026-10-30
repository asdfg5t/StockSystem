"""
一次性同步脚本：把 smart_results/*.json 里的真实 100 轮训练数据写回数据库。

背景：
  - smart_results/*.json 是 run_smart_train.py 跑出的 **真实** 100 轮训练数据
  - 但 DB 里的 train_task / train_metric 可能还是更早 run_paper_train.py 留下的
    200 轮脏数据，导致前端被迫硬截断到 100 显示
  - 本脚本把 DB 里 ts_code='smart_universal' 的 9 个任务（3模型×3步长）的训练
    指标全部用 JSON 重写，DB 与 JSON 完全对齐，前端 cap 逻辑就可以放心删掉

操作：
  对每个 smart_results/{model}_step{N}.json：
    1. 找 DB 里 (model_type, ts_code='smart_universal', predict_steps) 最新的
       已完成 task
    2. 把这个 task 的 train_metric / evaluate_result 全部清空
    3. 按 JSON 里 epoch_metrics 重新插入
    4. 更新 task 的 epochs / current_epoch / best_val_loss

执行：
    python backend/sync_smart_results_to_db.py

可选参数：
    --dry-run    只打印将要做什么，不真的写 DB
"""
import sys
import os
import json
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
RESULT_DIR = BASE_DIR / "smart_results"

sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))

from app.database import SessionLocal
from app.models.db_models import TrainTask, TrainMetric, EvaluateResult


MODELS = ["BiLSTM", "Transformer", "TFT"]
STEPS = [1, 3, 5]


def sync_one(db, model_type: str, predict_steps: int, dry_run: bool) -> bool:
    json_path = RESULT_DIR / f"{model_type}_step{predict_steps}.json"
    if not json_path.exists():
        print(f"  跳过：{json_path.name} 不存在")
        return False

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    epoch_metrics = data.get("epoch_metrics") or []
    epochs_trained = int(data.get("epochs_trained") or len(epoch_metrics))
    best_val_loss = data.get("best_val_loss")
    test_eval = data.get("test_evaluation") or {}

    if not epoch_metrics:
        print(f"  跳过：{json_path.name} 里 epoch_metrics 为空")
        return False

    task = (
        db.query(TrainTask)
        .filter(
            TrainTask.model_type == model_type,
            TrainTask.ts_code == "smart_universal",
            TrainTask.predict_steps == predict_steps,
            TrainTask.status == "completed",
        )
        .order_by(TrainTask.created_at.desc())
        .first()
    )

    if not task:
        print(
            f"  跳过：DB 里没有 {model_type}/smart_universal/step{predict_steps} 的"
            f" completed 任务（请先跑 run_smart_train.py 至少一次让 DB 有这条任务）"
        )
        return False

    old_metric_count = (
        db.query(TrainMetric).filter(TrainMetric.task_id == task.id).count()
    )
    old_eval_count = (
        db.query(EvaluateResult).filter(EvaluateResult.train_task_id == task.id).count()
    )

    print(
        f"  → task_id={task.id} | 旧 train_metric {old_metric_count} 条 / "
        f"evaluate_result {old_eval_count} 条 → 新 epoch_metrics "
        f"{len(epoch_metrics)} 条"
    )

    if dry_run:
        return True

    db.query(TrainMetric).filter(TrainMetric.task_id == task.id).delete(
        synchronize_session=False
    )
    db.query(EvaluateResult).filter(
        EvaluateResult.train_task_id == task.id
    ).delete(synchronize_session=False)

    task.epochs = epochs_trained
    task.current_epoch = epochs_trained
    if best_val_loss is not None:
        task.best_val_loss = round(float(best_val_loss), 6)

    for em in epoch_metrics:
        db.add(
            TrainMetric(
                task_id=task.id,
                epoch=int(em["epoch"]),
                train_loss=em.get("train_loss"),
                val_loss=em.get("val_loss"),
                train_mae=em.get("train_mae"),
                val_mae=em.get("val_mae"),
                train_rmse=em.get("train_rmse"),
                val_rmse=em.get("val_rmse"),
                learning_rate=em.get("learning_rate"),
            )
        )

    db.add(
        EvaluateResult(
            train_task_id=task.id,
            model_type=model_type,
            ts_code="smart_universal",
            predict_steps=predict_steps,
            dataset_type="test",
            mae=test_eval.get("mae"),
            mse=test_eval.get("mse"),
            rmse=test_eval.get("rmse"),
            mape=test_eval.get("mape"),
            smape=test_eval.get("smape"),
            r2=test_eval.get("r2"),
            direction_accuracy=test_eval.get("direction_accuracy"),
            max_error=test_eval.get("max_error"),
            median_ae=test_eval.get("median_ae"),
            explained_variance=test_eval.get("explained_variance"),
            pearson_corr=test_eval.get("pearson_corr"),
            accuracy_1pct=test_eval.get("accuracy_1pct"),
            accuracy_3pct=test_eval.get("accuracy_3pct"),
            accuracy_5pct=test_eval.get("accuracy_5pct"),
            win_rate=test_eval.get("win_rate"),
            profit_factor=test_eval.get("profit_factor"),
            sharpe_ratio=test_eval.get("sharpe_ratio"),
            max_drawdown=test_eval.get("max_drawdown"),
        )
    )

    db.commit()
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只打印将要做什么，不真的写 DB",
    )
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("  smart_results → DB 同步")
    print(f"  来源目录: {RESULT_DIR}")
    print(f"  模式: {'DRY RUN（不写 DB）' if args.dry_run else '真实写入 DB'}")
    print(f"{'='*60}\n")

    db = SessionLocal()
    success = 0
    try:
        for mt in MODELS:
            for step in STEPS:
                print(f"[{mt} step{step}]")
                if sync_one(db, mt, step, args.dry_run):
                    success += 1
                print()

        print(f"{'='*60}")
        print(f"  完成：{success}/9 个任务{'（dry-run）' if args.dry_run else ' 已同步到 DB'}")
        print(f"{'='*60}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
