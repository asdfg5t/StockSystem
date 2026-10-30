import sys
import os
from pathlib import Path

_backend_dir = str(Path(__file__).resolve().parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
os.chdir(_backend_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import dashboard, stock, data_collect, feature, model, train, predict, evaluate, system, backtest, analysis
from app.utils.logger import get_logger

logger = get_logger("main")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router, prefix=settings.API_PREFIX)
app.include_router(stock.router, prefix=settings.API_PREFIX)
app.include_router(data_collect.router, prefix=settings.API_PREFIX)
app.include_router(feature.router, prefix=settings.API_PREFIX)
app.include_router(model.router, prefix=settings.API_PREFIX)
app.include_router(train.router, prefix=settings.API_PREFIX)
app.include_router(predict.router, prefix=settings.API_PREFIX)
app.include_router(evaluate.router, prefix=settings.API_PREFIX)
app.include_router(system.router, prefix=settings.API_PREFIX)
app.include_router(backtest.router, prefix=settings.API_PREFIX)
app.include_router(analysis.router, prefix=settings.API_PREFIX)


@app.get("/")
def root():
    return {"project": settings.PROJECT_NAME, "version": settings.VERSION}


def _ensure_db_tables():
    """启动时自动修复数据库表结构"""
    try:
        import pymysql
        conn = pymysql.connect(
            host=settings.DB_HOST, port=settings.DB_PORT,
            user=settings.DB_USER, password=settings.DB_PASSWORD,
            database=settings.DB_NAME, charset="utf8mb4",
        )
        cursor = conn.cursor()
        fix_sqls = [
            """CREATE TABLE IF NOT EXISTS system_log (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                module VARCHAR(50) NOT NULL,
                level VARCHAR(10) NOT NULL,
                message TEXT NOT NULL,
                detail TEXT DEFAULT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_module (module),
                INDEX idx_level (level),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB""",
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
        ]
        for sql in fix_sqls:
            try:
                cursor.execute(sql)
            except Exception:
                pass
        # Fix system_log if columns missing
        try:
            cursor.execute("SELECT level FROM system_log LIMIT 1")
        except Exception:
            cursor.execute("DROP TABLE IF EXISTS system_log")
            cursor.execute(fix_sqls[0])
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.warning(f"数据库表检查跳过: {e}")


@app.on_event("startup")
async def startup():
    _ensure_db_tables()
    logger.info(f"{settings.PROJECT_NAME} v{settings.VERSION} 启动完成")


@app.on_event("shutdown")
async def shutdown():
    logger.info("服务关闭")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
