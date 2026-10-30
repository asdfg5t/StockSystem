"""
股票预测系统 - 启动脚本
用法: python startup.py [命令]

命令:
  initdb   - 初始化数据库(建库建表)
  server   - 启动后端API服务
  collect  - 采集股票基础列表 + 近三年日线数据
  train    - 训练所有模型(TFT/Transformer/BiLSTM, 1/3/5天)
  predict  - 使用训练好的模型进行预测
  all      - 依次执行: initdb → server(后台) → collect → train
"""

import sys
import os
import time
import subprocess
import pymysql
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
SQL_FILE = BACKEND_DIR / "sql" / "init.sql"

from app.config import settings

DB_HOST = settings.DB_HOST
DB_PORT = settings.DB_PORT
DB_USER = settings.DB_USER
DB_PASSWORD = settings.DB_PASSWORD
DB_NAME = settings.DB_NAME


def init_database():
    print("=" * 50)
    print("[1/4] 初始化数据库...")
    print("=" * 50)

    conn = pymysql.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD,
        charset="utf8mb4",
    )
    cursor = conn.cursor()

    with open(str(SQL_FILE), "r", encoding="utf-8") as f:
        sql_content = f.read()

    # The SQL template has a fixed database name; quote the configured identifier.
    sql_content = sql_content.replace("stock_prediction", "`" + DB_NAME.replace("`", "``") + "`")
    for statement in sql_content.split(";"):
        lines = [l for l in statement.strip().splitlines() if not l.strip().startswith("--")]
        cleaned = "\n".join(lines).strip()
        if not cleaned:
            continue
        try:
            cursor.execute(cleaned)
        except Exception as e:
            err_msg = str(e).lower()
            if "already exists" not in err_msg and "duplicate" not in err_msg:
                print(f"  SQL警告: {e}")

    conn.commit()
    cursor.close()
    conn.close()
    print("  数据库初始化完成!\n")


def start_server():
    print("=" * 50)
    print("[2/4] 启动后端API服务...")
    print("=" * 50)

    import uvicorn
    sys.path.insert(0, str(BACKEND_DIR))
    os.chdir(str(BACKEND_DIR))
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)


def run_collect():
    print("=" * 50)
    print("[2/4] 开始采集股票数据...")
    print("=" * 50)

    sys.path.insert(0, str(BACKEND_DIR))
    os.chdir(str(BACKEND_DIR))

    from app.database import SessionLocal
    from app.models.db_models import CollectTask
    from app.services.data_collector import collect_stock_basic, collect_daily_data

    db = SessionLocal()
    try:
        print("\n  >>> 采集A股股票基础列表...")
        task1 = CollectTask(
            task_name="启动脚本-股票列表采集",
            task_type="stock_basic",
            status="pending",
        )
        db.add(task1)
        db.commit()
        db.refresh(task1)
        collect_stock_basic(db, task1.id)
        print(f"  >>> 股票列表采集完成, 成功: {task1.success_count}\n")

        print("  >>> 采集近三年日线行情数据...")
        print("  >>> (数据量较大, 需要较长时间, 请耐心等待)")
        task2 = CollectTask(
            task_name="启动脚本-日线数据采集",
            task_type="daily",
            status="pending",
        )
        db.add(task2)
        db.commit()
        db.refresh(task2)
        collect_daily_data(db, task2.id)
        print(f"  >>> 日线数据采集完成, 成功: {task2.success_count}, 失败: {task2.fail_count}\n")
    finally:
        db.close()


def run_train(ts_code="000001.SZ"):
    print("=" * 50)
    print(f"[3/4] 开始训练模型 (股票: {ts_code})...")
    print("=" * 50)

    sys.path.insert(0, str(BACKEND_DIR))
    os.chdir(str(BACKEND_DIR))

    from app.database import SessionLocal
    from app.models.db_models import TrainTask
    from app.services.trainer import run_training

    db = SessionLocal()
    try:
        for model_type in ["BiLSTM", "Transformer", "TFT"]:
            for predict_steps in [1, 3, 5]:
                task_name = f"{model_type}-{ts_code}-{predict_steps}天预测"
                print(f"\n  >>> 训练: {task_name}")

                task = TrainTask(
                    task_name=task_name,
                    model_type=model_type,
                    ts_code=ts_code,
                    predict_steps=predict_steps,
                    lookback_window=30,
                    epochs=100,
                    batch_size=32,
                    learning_rate=0.001,
                    val_ratio=0.15,
                    test_ratio=0.15,
                    status="pending",
                )
                db.add(task)
                db.commit()
                db.refresh(task)

                run_training(db, task.id)

                db.refresh(task)
                print(f"  >>> {task_name} 完成, 状态: {task.status}")
                if task.best_val_loss:
                    print(f"      最优验证损失: {task.best_val_loss}")
    finally:
        db.close()

    print("\n  所有模型训练完成!\n")


def run_predict(ts_code="000001.SZ"):
    print("=" * 50)
    print(f"[4/4] 开始预测 (股票: {ts_code})...")
    print("=" * 50)

    sys.path.insert(0, str(BACKEND_DIR))
    os.chdir(str(BACKEND_DIR))

    from app.database import SessionLocal
    from app.models.db_models import PredictTask
    from app.services.predictor import run_prediction

    db = SessionLocal()
    try:
        for model_type in ["BiLSTM", "Transformer", "TFT"]:
            for predict_steps in [1, 3, 5]:
                task_name = f"预测-{model_type}-{ts_code}-{predict_steps}天"
                print(f"\n  >>> {task_name}")

                task = PredictTask(
                    task_name=task_name,
                    model_type=model_type,
                    ts_code=ts_code,
                    predict_steps=predict_steps,
                    status="pending",
                )
                db.add(task)
                db.commit()
                db.refresh(task)

                run_prediction(db, task.id)

                db.refresh(task)
                print(f"  >>> {task_name} 完成, 状态: {task.status}")
    finally:
        db.close()

    print("\n  所有预测完成!\n")


def run_all():
    ts_code = "000001.SZ"
    if len(sys.argv) > 2:
        ts_code = sys.argv[2]

    init_database()
    run_collect()
    run_train(ts_code)
    run_predict(ts_code)

    print("=" * 50)
    print("全部流程执行完毕!")
    print(f"  股票: {ts_code}")
    print("  模型: TFT / Transformer / BiLSTM")
    print("  步长: 1天 / 3天 / 5天")
    print("=" * 50)
    print("\n现在可以启动服务查看结果:")
    print("  后端: cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000")
    print("  前端: cd frontend && npm run dev")
    print("  访问: http://localhost:5173")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "initdb":
        init_database()
    elif cmd == "server":
        init_database()
        start_server()
    elif cmd == "collect":
        run_collect()
    elif cmd == "train":
        ts_code = sys.argv[2] if len(sys.argv) > 2 else "000001.SZ"
        run_train(ts_code)
    elif cmd == "predict":
        ts_code = sys.argv[2] if len(sys.argv) > 2 else "000001.SZ"
        run_predict(ts_code)
    elif cmd == "all":
        run_all()
    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
