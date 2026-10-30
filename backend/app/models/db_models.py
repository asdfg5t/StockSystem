from sqlalchemy import (
    Column, BigInteger, Integer, String, Text, DateTime, DECIMAL, SmallInteger
)
from sqlalchemy.sql import func
from app.database import Base


class StockBasic(Base):
    __tablename__ = "stock_basic"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ts_code = Column(String(20), nullable=False, unique=True)
    symbol = Column(String(10), nullable=False)
    name = Column(String(50), nullable=False)
    area = Column(String(20))
    industry = Column(String(50))
    market = Column(String(20))
    list_date = Column(String(10))
    list_status = Column(String(5), default="L")
    is_hs = Column(String(5))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class StockDaily(Base):
    __tablename__ = "stock_daily"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ts_code = Column(String(20), nullable=False)
    trade_date = Column(String(10), nullable=False)
    open = Column(DECIMAL(12, 4))
    high = Column(DECIMAL(12, 4))
    low = Column(DECIMAL(12, 4))
    close = Column(DECIMAL(12, 4))
    pre_close = Column(DECIMAL(12, 4))
    change = Column(DECIMAL(12, 4))
    pct_chg = Column(DECIMAL(12, 4))
    vol = Column(DECIMAL(18, 4))
    amount = Column(DECIMAL(18, 4))
    created_at = Column(DateTime, server_default=func.now())


class FeatureData(Base):
    __tablename__ = "feature_data"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ts_code = Column(String(20), nullable=False)
    trade_date = Column(String(10), nullable=False)
    feature_set = Column(Text)
    feature_version = Column(String(20), default="v1")
    created_at = Column(DateTime, server_default=func.now())


class CollectTask(Base):
    __tablename__ = "collect_task"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_name = Column(String(100), nullable=False)
    task_type = Column(String(30), nullable=False)
    ts_code = Column(String(20))
    start_date = Column(String(10))
    end_date = Column(String(10))
    status = Column(String(20), default="pending")
    total_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    progress = Column(DECIMAL(5, 2), default=0)
    error_msg = Column(Text)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CollectLog(Base):
    __tablename__ = "collect_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, nullable=False)
    ts_code = Column(String(20))
    status = Column(String(20), nullable=False)
    message = Column(Text)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class ModelConfig(Base):
    __tablename__ = "model_config"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_name = Column(String(50), nullable=False)
    model_type = Column(String(30), nullable=False)
    params = Column(Text)
    description = Column(String(200))
    is_active = Column(SmallInteger, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class TrainTask(Base):
    __tablename__ = "train_task"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_name = Column(String(100), nullable=False)
    model_type = Column(String(30), nullable=False)
    ts_code = Column(String(20), nullable=False)
    predict_steps = Column(Integer, nullable=False, default=1)
    lookback_window = Column(Integer, default=60)
    epochs = Column(Integer, default=100)
    batch_size = Column(Integer, default=32)
    learning_rate = Column(DECIMAL(10, 8), default=0.001)
    train_start_date = Column(String(10))
    train_end_date = Column(String(10))
    val_ratio = Column(DECIMAL(3, 2), default=0.15)
    test_ratio = Column(DECIMAL(3, 2), default=0.15)
    status = Column(String(20), default="pending")
    current_epoch = Column(Integer, default=0)
    best_val_loss = Column(DECIMAL(12, 6))
    model_path = Column(String(500))
    error_msg = Column(Text)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class TrainMetric(Base):
    __tablename__ = "train_metric"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, nullable=False)
    epoch = Column(Integer, nullable=False)
    train_loss = Column(DECIMAL(12, 6))
    val_loss = Column(DECIMAL(12, 6))
    train_mae = Column(DECIMAL(12, 6))
    val_mae = Column(DECIMAL(12, 6))
    train_rmse = Column(DECIMAL(12, 6))
    val_rmse = Column(DECIMAL(12, 6))
    learning_rate = Column(DECIMAL(12, 8))
    created_at = Column(DateTime, server_default=func.now())


class ModelFile(Base):
    __tablename__ = "model_file"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    train_task_id = Column(BigInteger)
    model_type = Column(String(30), nullable=False)
    ts_code = Column(String(20), nullable=False)
    predict_steps = Column(Integer, nullable=False)
    file_path = Column(String(500), nullable=False)
    scaler_path = Column(String(500))
    feature_config = Column(Text)
    metrics = Column(Text)
    is_best = Column(SmallInteger, default=0)
    file_size = Column(BigInteger, default=0)
    created_at = Column(DateTime, server_default=func.now())


class PredictTask(Base):
    __tablename__ = "predict_task"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_name = Column(String(100), nullable=False)
    model_type = Column(String(30), nullable=False)
    model_file_id = Column(BigInteger)
    ts_code = Column(String(20), nullable=False)
    predict_steps = Column(Integer, nullable=False, default=1)
    predict_date = Column(String(10))
    status = Column(String(20), default="pending")
    error_msg = Column(Text)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PredictResult(Base):
    __tablename__ = "predict_result"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, nullable=False)
    model_type = Column(String(30), nullable=False)
    ts_code = Column(String(20), nullable=False)
    predict_steps = Column(Integer, nullable=False)
    base_date = Column(String(10), nullable=False)
    target_date = Column(String(10), nullable=False)
    step_index = Column(Integer, nullable=False)
    predicted_close = Column(DECIMAL(12, 4), nullable=False)
    actual_close = Column(DECIMAL(12, 4))
    error = Column(DECIMAL(12, 4))
    error_pct = Column(DECIMAL(8, 4))
    created_at = Column(DateTime, server_default=func.now())


class EvaluateResult(Base):
    __tablename__ = "evaluate_result"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    train_task_id = Column(BigInteger)
    model_type = Column(String(30), nullable=False)
    ts_code = Column(String(20), nullable=False)
    predict_steps = Column(Integer, nullable=False)
    dataset_type = Column(String(20), nullable=False, default="test")
    mae = Column(DECIMAL(12, 6))
    mse = Column(DECIMAL(12, 6))
    rmse = Column(DECIMAL(12, 6))
    mape = Column(DECIMAL(12, 6))
    smape = Column(DECIMAL(12, 6))
    r2 = Column(DECIMAL(12, 6))
    direction_accuracy = Column(DECIMAL(8, 4))
    max_error = Column(DECIMAL(12, 6))
    median_ae = Column(DECIMAL(12, 6))
    explained_variance = Column(DECIMAL(12, 6))
    pearson_corr = Column(DECIMAL(12, 6))
    accuracy_1pct = Column(DECIMAL(8, 4))
    accuracy_3pct = Column(DECIMAL(8, 4))
    accuracy_5pct = Column(DECIMAL(8, 4))
    win_rate = Column(DECIMAL(8, 4))
    profit_factor = Column(DECIMAL(12, 6))
    sharpe_ratio = Column(DECIMAL(12, 6))
    max_drawdown = Column(DECIMAL(8, 4))
    actual_values = Column(Text)
    predicted_values = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    config_key = Column(String(100), nullable=False, unique=True)
    config_value = Column(Text, nullable=False)
    config_type = Column(String(20), default="string")
    description = Column(String(200))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SystemLog(Base):
    __tablename__ = "system_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    module = Column(String(50), nullable=False)
    level = Column(String(10), nullable=False)
    message = Column(Text, nullable=False)
    detail = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
