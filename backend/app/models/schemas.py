from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class ResponseBase(BaseModel):
    code: int = 200
    message: str = "success"
    data: Any = None


class PageResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Any = None
    total: int = 0
    page: int = 1
    page_size: int = 20


# ---- Stock ----
class StockBasicOut(BaseModel):
    id: int
    ts_code: str
    symbol: str
    name: str
    area: Optional[str] = None
    industry: Optional[str] = None
    market: Optional[str] = None
    list_date: Optional[str] = None
    list_status: Optional[str] = None

    class Config:
        from_attributes = True


class StockDailyOut(BaseModel):
    id: int
    ts_code: str
    trade_date: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    pre_close: Optional[float] = None
    change: Optional[float] = None
    pct_chg: Optional[float] = None
    vol: Optional[float] = None
    amount: Optional[float] = None

    class Config:
        from_attributes = True


# ---- Collect ----
class CollectTaskCreate(BaseModel):
    task_name: str
    task_type: str
    ts_code: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class CollectTaskOut(BaseModel):
    id: int
    task_name: str
    task_type: str
    ts_code: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str
    total_count: int
    success_count: int
    fail_count: int
    progress: float
    error_msg: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CollectLogOut(BaseModel):
    id: int
    task_id: int
    ts_code: Optional[str] = None
    status: str
    message: Optional[str] = None
    retry_count: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---- Train ----
class TrainTaskCreate(BaseModel):
    task_name: str
    model_type: str
    ts_code: str
    predict_steps: int = 1
    lookback_window: int = 60
    epochs: int = 100
    batch_size: int = 32
    learning_rate: float = 0.001
    train_start_date: Optional[str] = None
    train_end_date: Optional[str] = None
    val_ratio: float = 0.15
    test_ratio: float = 0.15


class TrainTaskOut(BaseModel):
    id: int
    task_name: str
    model_type: str
    ts_code: str
    predict_steps: int
    lookback_window: int
    epochs: int
    batch_size: int
    learning_rate: float
    status: str
    current_epoch: int
    best_val_loss: Optional[float] = None
    model_path: Optional[str] = None
    error_msg: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TrainMetricOut(BaseModel):
    id: int
    task_id: int
    epoch: int
    train_loss: Optional[float] = None
    val_loss: Optional[float] = None
    train_mae: Optional[float] = None
    val_mae: Optional[float] = None
    train_rmse: Optional[float] = None
    val_rmse: Optional[float] = None
    learning_rate: Optional[float] = None

    class Config:
        from_attributes = True


# ---- Model ----
class ModelConfigOut(BaseModel):
    id: int
    model_name: str
    model_type: str
    params: Optional[str] = None
    description: Optional[str] = None
    is_active: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ModelConfigUpdate(BaseModel):
    model_name: Optional[str] = None
    params: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[int] = None


class ModelFileOut(BaseModel):
    id: int
    train_task_id: Optional[int] = None
    model_type: str
    ts_code: str
    predict_steps: int
    file_path: str
    scaler_path: Optional[str] = None
    metrics: Optional[str] = None
    is_best: int
    file_size: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---- Predict ----
class PredictTaskCreate(BaseModel):
    task_name: str
    model_type: str
    ts_code: str
    predict_steps: int = 1
    model_file_id: Optional[int] = None
    predict_date: Optional[str] = None
    target_date: Optional[str] = None


class QuickPredictRequest(BaseModel):
    ts_code: str
    model_type: str = "TFT"
    base_date: Optional[str] = None
    predict_steps: Optional[int] = None
    target_date: Optional[str] = None


class PredictTaskOut(BaseModel):
    id: int
    task_name: str
    model_type: str
    model_file_id: Optional[int] = None
    ts_code: str
    predict_steps: int
    predict_date: Optional[str] = None
    status: str
    error_msg: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PredictResultOut(BaseModel):
    id: int
    task_id: int
    model_type: str
    ts_code: str
    predict_steps: int
    base_date: str
    target_date: str
    step_index: int
    predicted_close: float
    actual_close: Optional[float] = None
    error: Optional[float] = None
    error_pct: Optional[float] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---- Evaluate ----
class EvaluateResultOut(BaseModel):
    id: int
    train_task_id: Optional[int] = None
    model_type: str
    ts_code: str
    predict_steps: int
    dataset_type: str
    mae: Optional[float] = None
    mse: Optional[float] = None
    rmse: Optional[float] = None
    mape: Optional[float] = None
    smape: Optional[float] = None
    r2: Optional[float] = None
    direction_accuracy: Optional[float] = None
    max_error: Optional[float] = None
    median_ae: Optional[float] = None
    explained_variance: Optional[float] = None
    pearson_corr: Optional[float] = None
    accuracy_1pct: Optional[float] = None
    accuracy_3pct: Optional[float] = None
    accuracy_5pct: Optional[float] = None
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    actual_values: Optional[str] = None
    predicted_values: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---- System ----
class SystemConfigOut(BaseModel):
    id: int
    config_key: str
    config_value: str
    config_type: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class SystemConfigUpdate(BaseModel):
    config_value: str


class SystemLogOut(BaseModel):
    id: int
    module: str
    level: str
    message: str
    detail: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---- Feature ----
class FeatureComputeRequest(BaseModel):
    ts_code: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    version: str = "v1"


# ---- Dashboard ----
class DashboardStats(BaseModel):
    stock_count: int = 0
    daily_data_count: int = 0
    model_count: int = 0
    predict_count: int = 0
    latest_collect_task: Optional[CollectTaskOut] = None
    latest_train_task: Optional[TrainTaskOut] = None
    recent_predictions: List[PredictResultOut] = []
