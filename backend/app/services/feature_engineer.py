import json
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from app.models.db_models import StockDaily, FeatureData
from app.utils.logger import get_logger

logger = get_logger("feature")


def compute_features(
    db: Session, ts_code: str,
    start_date: str = None, end_date: str = None,
    version: str = "v1",
    save_to_db: bool = True,
) -> pd.DataFrame:
    """计算单只股票的完整特征集。save_to_db=False 时跳过数据库写入，大幅加速批量调用。"""
    query = db.query(StockDaily).filter(StockDaily.ts_code == ts_code)
    if start_date:
        query = query.filter(StockDaily.trade_date >= start_date)
    if end_date:
        query = query.filter(StockDaily.trade_date <= end_date)
    query = query.order_by(StockDaily.trade_date.asc())
    records = query.all()

    if not records or len(records) < 60:
        logger.warning(f"{ts_code} 数据不足60条, 无法计算特征")
        return pd.DataFrame()

    df = pd.DataFrame([{
        "trade_date": r.trade_date,
        "open": float(r.open) if r.open else np.nan,
        "high": float(r.high) if r.high else np.nan,
        "low": float(r.low) if r.low else np.nan,
        "close": float(r.close) if r.close else np.nan,
        "pre_close": float(r.pre_close) if r.pre_close else np.nan,
        "change": float(r.change) if r.change else np.nan,
        "pct_chg": float(r.pct_chg) if r.pct_chg else np.nan,
        "vol": float(r.vol) if r.vol else np.nan,
        "amount": float(r.amount) if r.amount else np.nan,
    } for r in records])

    df = _handle_missing(df)
    df = _add_ma_features(df)
    df = _add_ema_features(df)
    df = _add_macd(df)
    df = _add_kdj(df)
    df = _add_rsi(df)
    df = _add_boll(df)
    df = _add_cci(df)
    df = _add_atr(df)
    df = _add_obv(df)
    df = _add_roc(df)
    df = _add_mom(df)
    df = _add_time_features(df)
    df = _add_market_features(df)
    df = _handle_outliers(df)

    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)

    if save_to_db:
        _save_features_to_db(db, ts_code, df, version)

    logger.info(f"{ts_code} 特征计算完成, 共 {len(df)} 条, 特征数 {len(df.columns)}")
    return df


def _handle_missing(df: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].ffill().bfill()
    return df


def _handle_outliers(df: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        q1 = df[col].quantile(0.01)
        q99 = df[col].quantile(0.99)
        df[col] = df[col].clip(q1, q99)
    return df


def _add_ma_features(df: pd.DataFrame) -> pd.DataFrame:
    for window in [5, 10, 20, 30, 60]:
        df[f"ma_{window}"] = df["close"].rolling(window=window).mean()
        df[f"vol_ma_{window}"] = df["vol"].rolling(window=window).mean()
    df["ma5_ma20_cross"] = (df["ma_5"] - df["ma_20"]) / df["ma_20"]
    df["price_ma5_ratio"] = (df["close"] - df["ma_5"]) / df["ma_5"]
    df["price_ma20_ratio"] = (df["close"] - df["ma_20"]) / df["ma_20"]
    return df


def _add_ema_features(df: pd.DataFrame) -> pd.DataFrame:
    for span in [12, 26, 50]:
        df[f"ema_{span}"] = df["close"].ewm(span=span, adjust=False).mean()
    return df


def _add_macd(df: pd.DataFrame) -> pd.DataFrame:
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd_dif"] = ema12 - ema26
    df["macd_dea"] = df["macd_dif"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = 2 * (df["macd_dif"] - df["macd_dea"])
    return df


def _add_kdj(df: pd.DataFrame) -> pd.DataFrame:
    low_min = df["low"].rolling(window=9).min()
    high_max = df["high"].rolling(window=9).max()
    rsv = (df["close"] - low_min) / (high_max - low_min + 1e-8) * 100
    df["kdj_k"] = rsv.ewm(com=2, adjust=False).mean()
    df["kdj_d"] = df["kdj_k"].ewm(com=2, adjust=False).mean()
    df["kdj_j"] = 3 * df["kdj_k"] - 2 * df["kdj_d"]
    return df


def _add_rsi(df: pd.DataFrame) -> pd.DataFrame:
    for period in [6, 12, 24]:
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / (avg_loss + 1e-8)
        df[f"rsi_{period}"] = 100 - (100 / (1 + rs))
    return df


def _add_boll(df: pd.DataFrame) -> pd.DataFrame:
    ma20 = df["close"].rolling(window=20).mean()
    std20 = df["close"].rolling(window=20).std()
    df["boll_upper"] = ma20 + 2 * std20
    df["boll_mid"] = ma20
    df["boll_lower"] = ma20 - 2 * std20
    df["boll_width"] = (df["boll_upper"] - df["boll_lower"]) / (df["boll_mid"] + 1e-8)
    df["boll_pct"] = (df["close"] - df["boll_lower"]) / (
        df["boll_upper"] - df["boll_lower"] + 1e-8
    )
    return df


def _add_cci(df: pd.DataFrame) -> pd.DataFrame:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    ma_tp = tp.rolling(window=14).mean()
    md = tp.rolling(window=14).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    df["cci"] = (tp - ma_tp) / (0.015 * md + 1e-8)
    return df


def _add_atr(df: pd.DataFrame) -> pd.DataFrame:
    high_low = df["high"] - df["low"]
    high_prev_close = (df["high"] - df["pre_close"]).abs()
    low_prev_close = (df["low"] - df["pre_close"]).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    df["atr_14"] = tr.rolling(window=14).mean()
    df["atr_ratio"] = df["atr_14"] / (df["close"] + 1e-8)
    return df


def _add_obv(df: pd.DataFrame) -> pd.DataFrame:
    obv = [0]
    for i in range(1, len(df)):
        if df["close"].iloc[i] > df["close"].iloc[i - 1]:
            obv.append(obv[-1] + df["vol"].iloc[i])
        elif df["close"].iloc[i] < df["close"].iloc[i - 1]:
            obv.append(obv[-1] - df["vol"].iloc[i])
        else:
            obv.append(obv[-1])
    df["obv"] = obv
    df["obv_ma5"] = df["obv"].rolling(window=5).mean()
    return df


def _add_roc(df: pd.DataFrame) -> pd.DataFrame:
    for period in [5, 10, 20]:
        df[f"roc_{period}"] = (
            (df["close"] - df["close"].shift(period))
            / (df["close"].shift(period) + 1e-8) * 100
        )
    return df


def _add_mom(df: pd.DataFrame) -> pd.DataFrame:
    for period in [5, 10, 20]:
        df[f"mom_{period}"] = df["close"] - df["close"].shift(period)
    return df


def _add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    dates = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    df["day_of_week"] = dates.dt.dayofweek
    df["day_of_month"] = dates.dt.day
    df["month"] = dates.dt.month
    df["quarter"] = dates.dt.quarter
    df["week_of_year"] = dates.dt.isocalendar().week.astype(int)
    df["day_of_week_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 5)
    df["day_of_week_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 5)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    return df


def _add_market_features(df: pd.DataFrame) -> pd.DataFrame:
    df["return_1d"] = df["close"].pct_change(1)
    df["return_5d"] = df["close"].pct_change(5)
    df["return_10d"] = df["close"].pct_change(10)
    df["volatility_5d"] = df["return_1d"].rolling(window=5).std()
    df["volatility_10d"] = df["return_1d"].rolling(window=10).std()
    df["volatility_20d"] = df["return_1d"].rolling(window=20).std()
    df["vol_change"] = df["vol"].pct_change(1)
    df["amount_change"] = df["amount"].pct_change(1)
    df["high_low_ratio"] = (df["high"] - df["low"]) / (df["low"] + 1e-8)
    df["close_open_ratio"] = (df["close"] - df["open"]) / (df["open"] + 1e-8)
    df["upper_shadow"] = (df["high"] - df[["open", "close"]].max(axis=1)) / (
        df["high"] - df["low"] + 1e-8
    )
    df["lower_shadow"] = (df[["open", "close"]].min(axis=1) - df["low"]) / (
        df["high"] - df["low"] + 1e-8
    )
    df["vol_price_corr"] = (
        df["vol"].rolling(window=20).corr(df["close"])
    )
    return df


def _save_features_to_db(
    db: Session, ts_code: str, df: pd.DataFrame, version: str
):
    """将特征数据保存到数据库"""
    feature_cols = [c for c in df.columns if c != "trade_date"]

    for _, row in df.iterrows():
        trade_date = row["trade_date"]
        features = {col: float(row[col]) if pd.notna(row[col]) else None
                     for col in feature_cols}

        existing = db.query(FeatureData).filter(
            FeatureData.ts_code == ts_code,
            FeatureData.trade_date == trade_date,
            FeatureData.feature_version == version,
        ).first()

        if existing:
            existing.feature_set = json.dumps(features)
        else:
            fd = FeatureData(
                ts_code=ts_code,
                trade_date=trade_date,
                feature_set=json.dumps(features),
                feature_version=version,
            )
            db.add(fd)

    db.commit()


def get_feature_columns() -> list:
    """返回所有特征列名（供前端展示）"""
    return [
        "open", "high", "low", "close", "pre_close", "change", "pct_chg",
        "vol", "amount",
        "ma_5", "ma_10", "ma_20", "ma_30", "ma_60",
        "vol_ma_5", "vol_ma_10", "vol_ma_20", "vol_ma_30", "vol_ma_60",
        "ma5_ma20_cross", "price_ma5_ratio", "price_ma20_ratio",
        "ema_12", "ema_26", "ema_50",
        "macd_dif", "macd_dea", "macd_hist",
        "kdj_k", "kdj_d", "kdj_j",
        "rsi_6", "rsi_12", "rsi_24",
        "boll_upper", "boll_mid", "boll_lower", "boll_width", "boll_pct",
        "cci", "atr_14", "atr_ratio",
        "obv", "obv_ma5",
        "roc_5", "roc_10", "roc_20",
        "mom_5", "mom_10", "mom_20",
        "day_of_week", "day_of_month", "month", "quarter", "week_of_year",
        "day_of_week_sin", "day_of_week_cos", "month_sin", "month_cos",
        "return_1d", "return_5d", "return_10d",
        "volatility_5d", "volatility_10d", "volatility_20d",
        "vol_change", "amount_change",
        "high_low_ratio", "close_open_ratio",
        "upper_shadow", "lower_shadow", "vol_price_corr",
    ]
