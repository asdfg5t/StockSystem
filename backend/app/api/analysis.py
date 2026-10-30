import json
import os
import numpy as np
import joblib
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import MODEL_DIR
from app.models.db_models import ModelFile, EvaluateResult, StockBasic, StockDaily
from app.models.schemas import ResponseBase
from app.services.feature_engineer import compute_features, get_feature_columns
from app.utils.logger import get_logger

logger = get_logger("analysis")
router = APIRouter(prefix="/analysis", tags=["分析中心"])


@router.get("/pca_importance")
def get_pca_importance(
    ts_code: str = Query("000001.SZ"),
    model_type: str = Query("BiLSTM"),
    predict_steps: int = Query(1),
):
    """
    特征重要性分析。
    优先级与预测一致：smart_universal > universal > 单股票。
    - 存在 PCA：返回标准的方差解释比 + 各主成分 Top-5 原始特征。
    - 不存在 PCA（如 smart_universal）：根据 feature_config 返回互信息精选的特征排序。
    """
    candidates = [
        ("smart_universal", f"smart_universal_{model_type}_step{predict_steps}"),
        ("universal", f"universal_{model_type}_step{predict_steps}"),
        (ts_code, f"{ts_code}_{model_type}_step{predict_steps}"),
    ]

    # 1) 先按候选优先级找 PCA 文件
    for code, prefix in candidates:
        pca_path = str(MODEL_DIR / f"{prefix}_pca.pkl")
        if not os.path.exists(pca_path):
            continue
        pca = joblib.load(pca_path)
        # 先尝试取该模型保存的 feature_config，否则 fallback 到全量特征名
        feature_names = _load_feature_columns(db=None, code=code, model_type=model_type,
                                              predict_steps=predict_steps) or get_feature_columns()

        explained = pca.explained_variance_ratio_.tolist()
        cumulative = np.cumsum(pca.explained_variance_ratio_).tolist()

        components = pca.components_
        n_components = min(len(explained), 10)
        top_features = []
        for i in range(n_components):
            abs_weights = np.abs(components[i])
            n_feat = min(len(feature_names), len(abs_weights))
            indices = np.argsort(abs_weights[:n_feat])[::-1][:5]
            top = [
                {"feature": feature_names[idx] if idx < len(feature_names) else f"feat_{idx}",
                 "weight": round(float(components[i][idx]), 4)}
                for idx in indices
            ]
            top_features.append({
                "component": i + 1,
                "explained_ratio": round(float(explained[i]) * 100, 2),
                "top_features": top,
            })

        return ResponseBase(data={
            "mode": "pca",
            "model_scope": code,
            "explained_ratio": [round(float(x) * 100, 2) for x in explained],
            "cumulative_ratio": [round(float(x) * 100, 2) for x in cumulative],
            "top_features_per_component": top_features,
            "total_components": len(explained),
            "total_variance_explained": round(float(cumulative[-1]) * 100, 2) if cumulative else 0,
        })

    # 2) 无 PCA：尝试用最佳模型的 feature_config（适配 smart_universal）
    return _feature_selection_importance_response(model_type, ts_code, predict_steps)


def _feature_selection_importance_response(model_type: str, ts_code: str, predict_steps: int):
    """对于无 PCA 的智能模型（smart_universal），按 feature_config 顺序返回特征重要性。"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        model_file = _find_best_model(db, model_type, ts_code, predict_steps)
        if not model_file or not model_file.feature_config:
            return ResponseBase(
                code=404,
                message="未找到任何已训练模型（既无 PCA 也无智能模型），请先完成训练",
            )
        try:
            feats = json.loads(model_file.feature_config)
        except Exception:
            return ResponseBase(code=500, message="模型 feature_config 解析失败")
        if not feats:
            return ResponseBase(code=404, message="模型未保存特征列表")

        # feature_config 已按互信息排序保存（Top-K 精选），把它分成最多 6 段做"伪主成分"展示
        n = len(feats)
        chunk = max(5, (n + 5) // 6)
        chunks = [feats[i:i + chunk] for i in range(0, n, chunk)]
        total = float(n) or 1.0
        top_features_per_component = []
        cum = 0.0
        explained_ratio = []
        cumulative_ratio = []
        for i, group in enumerate(chunks):
            ratio = len(group) / total * 100
            cum += ratio
            explained_ratio.append(round(ratio, 2))
            cumulative_ratio.append(round(cum, 2))
            top_features_per_component.append({
                "component": i + 1,
                "explained_ratio": round(ratio, 2),
                "top_features": [
                    {"feature": f, "weight": round(1.0 - idx / max(len(group) - 1, 1) * 0.6, 4)}
                    for idx, f in enumerate(group[:5])
                ],
            })

        return ResponseBase(data={
            "mode": "feature_selection",
            "model_scope": model_file.ts_code,
            "explained_ratio": explained_ratio,
            "cumulative_ratio": cumulative_ratio,
            "top_features_per_component": top_features_per_component,
            "total_components": len(chunks),
            "total_variance_explained": 100.0,
            "selected_features": feats,
            "note": "该模型未使用 PCA，展示的是互信息精选的 Top 特征排序",
        })
    finally:
        db.close()


def _load_feature_columns(db, code: str, model_type: str, predict_steps: int):
    """尝试从对应 model_file 记录中读取 feature_config（用于给 PCA 主成分做反查命名）。"""
    from app.database import SessionLocal
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        mf = db.query(ModelFile).filter(
            ModelFile.ts_code == code,
            ModelFile.model_type == model_type,
            ModelFile.predict_steps == predict_steps,
            ModelFile.is_best == 1,
        ).order_by(ModelFile.created_at.desc()).first()
        if mf and mf.feature_config:
            try:
                return json.loads(mf.feature_config)
            except Exception:
                return None
        return None
    finally:
        if own_db:
            db.close()


@router.get("/model_features")
def get_model_features(
    ts_code: str = Query("000001.SZ"),
    model_type: str = Query("BiLSTM"),
    predict_steps: int = Query(1),
    db: Session = Depends(get_db),
):
    """
    返回当前 (ts_code, model_type, predict_steps) 实际会被使用的最佳模型所支持的特征列表，
    供前端 What-If/敏感度分析等页面动态填充下拉菜单。
    """
    model_file = _find_best_model(db, model_type, ts_code, predict_steps)
    if not model_file or not model_file.feature_config:
        return ResponseBase(data={
            "model_scope": None,
            "features": [],
            "is_universal": False,
        })
    try:
        feats = json.loads(model_file.feature_config)
    except Exception:
        feats = []
    return ResponseBase(data={
        "model_scope": model_file.ts_code,
        "features": feats,
        "is_universal": model_file.ts_code in ("universal", "smart_universal"),
    })


@router.get("/feature_correlation")
def get_feature_correlation(
    ts_code: str = Query("000001.SZ"),
    db: Session = Depends(get_db),
):
    feature_df = compute_features(db, ts_code)
    if feature_df.empty:
        return ResponseBase(code=404, message="特征数据为空")

    numeric_df = feature_df.select_dtypes(include=[np.number])
    cols = numeric_df.columns.tolist()[:30]
    sub_df = numeric_df[cols]
    corr = sub_df.corr().round(3)

    return ResponseBase(data={
        "features": cols,
        "matrix": corr.values.tolist(),
    })


@router.get("/multi_stock_eval")
def get_multi_stock_eval(
    model_type: str = Query(""),
    db: Session = Depends(get_db),
):
    query = db.query(EvaluateResult).filter(EvaluateResult.dataset_type == "test")
    if model_type:
        query = query.filter(EvaluateResult.model_type == model_type)

    results = query.order_by(EvaluateResult.created_at.desc()).all()

    stock_map = {}
    for r in results:
        key = f"{r.ts_code}_{r.model_type}_{r.predict_steps}"
        if key not in stock_map:
            stock = db.query(StockBasic).filter(StockBasic.ts_code == r.ts_code).first()
            stock_map[key] = {
                "ts_code": r.ts_code,
                "name": stock.name if stock else r.ts_code,
                "industry": stock.industry if stock else "",
                "model_type": r.model_type,
                "predict_steps": r.predict_steps,
                "mae": float(r.mae) if r.mae else None,
                "rmse": float(r.rmse) if r.rmse else None,
                "mape": float(r.mape) if r.mape else None,
                "r2": float(r.r2) if r.r2 else None,
                "accuracy_3pct": float(r.accuracy_3pct) if r.accuracy_3pct else None,
                "sharpe_ratio": float(r.sharpe_ratio) if r.sharpe_ratio else None,
                "win_rate": float(r.win_rate) if r.win_rate else None,
            }

    items = list(stock_map.values())

    industries = {}
    for item in items:
        ind = item.get("industry") or "未知"
        if ind not in industries:
            industries[ind] = []
        industries[ind].append(item)

    industry_summary = []
    for ind, stocks in industries.items():
        r2_vals = [s["r2"] for s in stocks if s["r2"] is not None]
        mape_vals = [s["mape"] for s in stocks if s["mape"] is not None]
        sharpe_vals = [s["sharpe_ratio"] for s in stocks if s["sharpe_ratio"] is not None]
        industry_summary.append({
            "industry": ind,
            "count": len(stocks),
            "avg_r2": round(float(np.mean(r2_vals)), 4) if r2_vals else None,
            "avg_mape": round(float(np.mean(mape_vals)), 4) if mape_vals else None,
            "avg_sharpe": round(float(np.mean(sharpe_vals)), 4) if sharpe_vals else None,
        })

    return ResponseBase(data={
        "stocks": items,
        "industry_summary": industry_summary,
    })


@router.get("/portfolio_suggest")
def get_portfolio_suggestion(
    model_type: str = Query("BiLSTM"),
    predict_steps: int = Query(1),
    top_n: int = Query(5),
    db: Session = Depends(get_db),
):
    results = db.query(EvaluateResult).filter(
        EvaluateResult.model_type == model_type,
        EvaluateResult.predict_steps == predict_steps,
        EvaluateResult.dataset_type == "test",
    ).order_by(EvaluateResult.created_at.desc()).all()

    seen = set()
    unique = []
    for r in results:
        if r.ts_code not in seen:
            seen.add(r.ts_code)
            stock = db.query(StockBasic).filter(StockBasic.ts_code == r.ts_code).first()
            sharpe = float(r.sharpe_ratio) if r.sharpe_ratio else 0
            r2 = float(r.r2) if r.r2 else 0
            score = sharpe * 0.6 + r2 * 0.4
            unique.append({
                "ts_code": r.ts_code,
                "name": stock.name if stock else r.ts_code,
                "industry": stock.industry if stock else "",
                "r2": round(r2, 4),
                "mape": round(float(r.mape), 4) if r.mape else None,
                "sharpe_ratio": round(sharpe, 4),
                "accuracy_3pct": round(float(r.accuracy_3pct), 2) if r.accuracy_3pct else None,
                "score": round(float(score), 4),
            })

    unique.sort(key=lambda x: x["score"], reverse=True)
    return ResponseBase(data={
        "suggestions": unique[:top_n],
        "model_type": model_type,
        "predict_steps": predict_steps,
    })


@router.get("/error_distribution")
def get_error_distribution(
    ts_code: str = Query("000001.SZ"),
    model_type: str = Query(""),
    predict_steps: int = Query(1),
    db: Session = Depends(get_db),
):
    """预测误差分布分析"""
    query = db.query(EvaluateResult).filter(
        EvaluateResult.ts_code == ts_code,
        EvaluateResult.predict_steps == predict_steps,
        EvaluateResult.dataset_type == "test",
    )
    if model_type:
        query = query.filter(EvaluateResult.model_type == model_type)

    results = query.order_by(EvaluateResult.created_at.desc()).all()

    models_data = {}
    for r in results:
        if r.model_type in models_data:
            continue
        actual = _safe_json(r.actual_values)
        predicted = _safe_json(r.predicted_values)
        if not actual or not predicted:
            continue

        n = min(len(actual), len(predicted))
        a = np.array(actual[:n])
        p = np.array(predicted[:n])
        errors = p - a
        pct_errors = errors / (np.abs(a) + 1e-8) * 100

        hist_counts, hist_edges = np.histogram(pct_errors, bins=20)

        models_data[r.model_type] = {
            "errors": np.round(errors, 4).tolist(),
            "pct_errors": np.round(pct_errors, 4).tolist(),
            "stats": {
                "mean": round(float(np.mean(errors)), 4),
                "std": round(float(np.std(errors)), 4),
                "median": round(float(np.median(errors)), 4),
                "skewness": round(float(_skewness(errors)), 4),
                "kurtosis": round(float(_kurtosis(errors)), 4),
                "q25": round(float(np.percentile(pct_errors, 25)), 4),
                "q75": round(float(np.percentile(pct_errors, 75)), 4),
                "min_pct": round(float(np.min(pct_errors)), 4),
                "max_pct": round(float(np.max(pct_errors)), 4),
            },
            "histogram": {
                "counts": hist_counts.tolist(),
                "edges": np.round(hist_edges, 2).tolist(),
            },
        }

    return ResponseBase(data=models_data)


@router.get("/model_drift")
def get_model_drift(
    ts_code: str = Query("000001.SZ"),
    model_type: str = Query("BiLSTM"),
    predict_steps: int = Query(1),
    window_size: int = Query(20, ge=5, le=100),
    db: Session = Depends(get_db),
):
    """模型漂移监控 — 滑动窗口评估精度变化"""
    eval_res = db.query(EvaluateResult).filter(
        EvaluateResult.ts_code == ts_code,
        EvaluateResult.model_type == model_type,
        EvaluateResult.predict_steps == predict_steps,
        EvaluateResult.dataset_type == "test",
    ).order_by(EvaluateResult.created_at.desc()).first()

    if not eval_res:
        return ResponseBase(code=404, message="未找到评估数据")

    actual = np.array(_safe_json(eval_res.actual_values))
    predicted = np.array(_safe_json(eval_res.predicted_values))
    n = min(len(actual), len(predicted))
    if n < window_size:
        return ResponseBase(code=400, message=f"数据量({n})小于窗口大小({window_size})")

    actual = actual[:n]
    predicted = predicted[:n]

    windows = []
    for start in range(0, n - window_size + 1, max(1, window_size // 2)):
        end = start + window_size
        a_win = actual[start:end]
        p_win = predicted[start:end]
        errs = np.abs(a_win - p_win)
        pct_errs = errs / (np.abs(a_win) + 1e-8) * 100
        ss_res = np.sum((a_win - p_win) ** 2)
        ss_tot = np.sum((a_win - np.mean(a_win)) ** 2)
        r2 = 1 - ss_res / (ss_tot + 1e-8) if ss_tot > 0 else 0

        windows.append({
            "start": start,
            "end": end,
            "label": f"{start + 1}-{end}",
            "mae": round(float(np.mean(errs)), 4),
            "mape": round(float(np.mean(pct_errs)), 4),
            "r2": round(float(r2), 4),
            "accuracy_3pct": round(float(np.mean(pct_errs <= 3) * 100), 2),
        })

    return ResponseBase(data={
        "model_type": model_type,
        "ts_code": ts_code,
        "window_size": window_size,
        "total_samples": n,
        "windows": windows,
    })


@router.get("/whatif")
def whatif_analysis(
    ts_code: str = Query("000001.SZ"),
    model_type: str = Query("BiLSTM"),
    predict_steps: int = Query(1),
    feature_name: str = Query("vol"),
    multipliers: str = Query("0.5,0.8,1.0,1.2,1.5,2.0"),
    db: Session = Depends(get_db),
):
    """What-If 情景分析（支持通用模型回退）"""
    import torch
    from app.core.data_processor import TimeSeriesProcessor
    from app.services.trainer import _build_model

    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model_file = _find_best_model(db, model_type, ts_code, predict_steps)
    if not model_file:
        return ResponseBase(code=404, message="未找到模型文件，请先训练模型")

    if not model_file.scaler_path or not model_file.feature_config:
        return ResponseBase(
            code=400,
            message="模型文件缺少 scaler 或特征配置信息，请重新训练该模型",
        )

    try:
        scaler_info = json.loads(model_file.scaler_path)
        feature_columns = json.loads(model_file.feature_config)
        is_universal = model_file.ts_code in ("universal", "smart_universal")

        processor = TimeSeriesProcessor(lookback=30, predict_steps=predict_steps)
        processor.load_scalers(scaler_info["feature"], scaler_info["target"])
        processor.feature_columns = feature_columns

        feature_df = compute_features(db, ts_code, save_to_db=False)
        if feature_df.empty:
            return ResponseBase(code=404, message=f"股票 {ts_code} 特征数据为空，请确认已采集日线数据")

        exclude = ["trade_date"]
        raw_df = feature_df.drop(columns=[c for c in exclude if c in feature_df.columns])
        if list(raw_df.columns) != feature_columns:
            raw_df = raw_df[feature_columns]

        if feature_name not in raw_df.columns:
            available = list(raw_df.columns)
            preview = "、".join(available[:8])
            extra = f"等共 {len(available)} 个" if len(available) > 8 else ""
            return ResponseBase(
                code=400,
                message=(
                    f"当前模型（scope={model_file.ts_code}）未包含特征「{feature_name}」。"
                    f"可用特征：{preview}{extra}"
                ),
                data={"available_features": available, "model_scope": model_file.ts_code},
            )

        base_features = raw_df.values.astype(np.float32)
        close_idx = list(raw_df.columns).index("close")
        feat_idx = list(raw_df.columns).index(feature_name)
        base_val = float(base_features[-1, feat_idx])

        scaled_base = processor.feature_scaler.transform(base_features)
        if processor.pca is not None:
            scaled_base = processor.pca.transform(scaled_base).astype(np.float32)
        if is_universal and processor.stock_id_map:
            num_stocks = max(len(processor.stock_id_map), 1)
            embed_dim = min(16, max(4, num_stocks // 100))
            sid = processor.stock_id_map.get(ts_code, 0)
            sid_feature = np.full(
                (len(scaled_base), embed_dim),
                sid / max(num_stocks, 1),
                dtype=np.float32,
            )
            scaled_base = np.concatenate([scaled_base, sid_feature], axis=1)

        input_size = scaled_base.shape[1]
        model = _build_model(model_type, input_size, predict_steps)
        model.load_state_dict(torch.load(model_file.file_path, map_location=DEVICE))
        model = model.to(DEVICE)
        model.eval()

        mults = [float(m.strip()) for m in multipliers.split(",")]
        scenarios = []

        for mult in mults:
            modified = base_features.copy()
            modified[:, feat_idx] = base_features[:, feat_idx] * mult

            scaled = processor.feature_scaler.transform(modified)
            if processor.pca is not None:
                scaled = processor.pca.transform(scaled).astype(np.float32)
            if is_universal and processor.stock_id_map:
                scaled = np.concatenate([scaled, sid_feature], axis=1)
            X = scaled[-30:].reshape(1, 30, -1)

            last_close = float(modified[-1, close_idx])
            processor.test_base_prices = np.array([last_close])

            with torch.no_grad():
                pred = model(torch.FloatTensor(X).to(DEVICE)).cpu().numpy().flatten()
            prices = processor.inverse_transform_target(pred)

            scenarios.append({
                "multiplier": mult,
                "feature_value": round(base_val * mult, 4),
                "predicted_prices": np.round(prices, 4).tolist(),
            })

        return ResponseBase(data={
            "feature_name": feature_name,
            "base_value": round(base_val, 4),
            "scenarios": scenarios,
        })

    except Exception as e:
        logger.error(f"情景分析异常: {e}", exc_info=True)
        return ResponseBase(code=500, message=f"情景分析失败: {str(e)[:200]}")


def _find_best_model(db: Session, model_type: str, ts_code: str, predict_steps: int):
    """按优先级查找模型：智能通用 > 通用 > 单股票（与 predictor 逻辑一致）"""
    for code in ["smart_universal", "universal", ts_code]:
        found = db.query(ModelFile).filter(
            ModelFile.model_type == model_type,
            ModelFile.ts_code == code,
            ModelFile.predict_steps == predict_steps,
            ModelFile.is_best == 1,
        ).order_by(ModelFile.created_at.desc()).first()
        if found and found.scaler_path and found.feature_config:
            return found
    return None


def _safe_json(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return []


def _skewness(arr):
    n = len(arr)
    if n < 3:
        return 0
    m = np.mean(arr)
    s = np.std(arr)
    if s < 1e-8:
        return 0
    return np.mean(((arr - m) / s) ** 3)


def _kurtosis(arr):
    n = len(arr)
    if n < 4:
        return 0
    m = np.mean(arr)
    s = np.std(arr)
    if s < 1e-8:
        return 0
    return np.mean(((arr - m) / s) ** 4) - 3
