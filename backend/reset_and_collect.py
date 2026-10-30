"""
清空日线数据 + 旧文件，然后重新全量采集3年数据
"""
import sys
import os
import shutil
import pymysql
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
DAILY_DIR = BASE_DIR / "data" / "raw" / "daily"

from app.config import settings

DB_HOST = settings.DB_HOST
DB_PORT = settings.DB_PORT
DB_USER = settings.DB_USER
DB_PASSWORD = settings.DB_PASSWORD
DB_NAME = settings.DB_NAME


def reset_data():
    print("=" * 50)
    print("[1/3] 清空数据库日线数据...")
    print("=" * 50)

    conn = pymysql.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, charset="utf8mb4",
    )
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM stock_daily")
    count = cursor.fetchone()[0]
    print(f"  当前 stock_daily 表有 {count} 条记录")

    cursor.execute("TRUNCATE TABLE stock_daily")
    cursor.execute("DELETE FROM collect_task WHERE task_type = 'daily'")
    cursor.execute("DELETE FROM collect_log WHERE task_id NOT IN (SELECT id FROM collect_task)")
    conn.commit()

    cursor.close()
    conn.close()
    print("  数据库日线数据已清空!\n")


def reset_files():
    print("=" * 50)
    print("[2/3] 清空旧的日线文件...")
    print("=" * 50)

    if DAILY_DIR.exists():
        file_count = len(list(DAILY_DIR.glob("*.txt")))
        shutil.rmtree(DAILY_DIR)
        print(f"  已删除 {file_count} 个日线文件")
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    print("  日线文件目录已重建!\n")


def run_full_collect():
    print("=" * 50)
    print("[3/3] 开始全量采集3年日线数据...")
    print("  (5000+只股票, 预计需要较长时间)")
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
            task_name="重置-股票列表采集",
            task_type="stock_basic",
            status="pending",
        )
        db.add(task1)
        db.commit()
        db.refresh(task1)
        collect_stock_basic(db, task1.id)
        print(f"  >>> 股票列表采集完成, 成功: {task1.success_count}\n")

        print("  >>> 开始全量采集近三年日线行情数据...")
        task2 = CollectTask(
            task_name="重置-全量日线数据采集",
            task_type="daily",
            status="pending",
        )
        db.add(task2)
        db.commit()
        db.refresh(task2)
        collect_daily_data(db, task2.id)

        db.refresh(task2)
        print(f"\n  >>> 日线数据采集完成!")
        print(f"      成功: {task2.success_count}, 失败: {task2.fail_count}")
        print(f"      状态: {task2.status}")
    finally:
        db.close()


if __name__ == "__main__":
    print("\n*** 股票日线数据重置 & 全量重新采集 ***\n")
    reset_data()
    reset_files()
    run_full_collect()
    print("\n*** 全部完成! ***")
