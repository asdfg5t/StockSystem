import threading
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db, SessionLocal
from app.models.db_models import FeatureData
from app.models.schemas import ResponseBase, FeatureComputeRequest
from app.services.feature_engineer import compute_features, get_feature_columns
from app.utils.logger import get_logger

logger = get_logger("feature_api")
router = APIRouter(prefix="/feature", tags=["特征工程"])


@router.post("/compute")
def trigger_feature_compute(req: FeatureComputeRequest, db: Session = Depends(get_db)):
    def _run():
        session = SessionLocal()
        try:
            compute_features(
                session, req.ts_code, req.start_date, req.end_date, req.version
            )
        finally:
            session.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return ResponseBase(message=f"特征计算任务已启动: {req.ts_code}")


@router.get("/columns")
def get_columns():
    return ResponseBase(data=get_feature_columns())


@router.get("/data/{ts_code}")
def get_feature_data(
    ts_code: str,
    start_date: str = Query(""),
    end_date: str = Query(""),
    version: str = Query("v1"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(FeatureData).filter(
        FeatureData.ts_code == ts_code,
        FeatureData.feature_version == version,
    )
    if start_date:
        query = query.filter(FeatureData.trade_date >= start_date)
    if end_date:
        query = query.filter(FeatureData.trade_date <= end_date)

    total = query.count()
    items = query.order_by(FeatureData.trade_date.asc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return ResponseBase(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [{
            "id": f.id,
            "ts_code": f.ts_code,
            "trade_date": f.trade_date,
            "feature_set": f.feature_set,
            "feature_version": f.feature_version,
        } for f in items],
    })


@router.get("/stats/{ts_code}")
def get_feature_stats(
    ts_code: str,
    version: str = Query("v1"),
    db: Session = Depends(get_db),
):
    count = db.query(func.count(FeatureData.id)).filter(
        FeatureData.ts_code == ts_code,
        FeatureData.feature_version == version,
    ).scalar()

    min_date = db.query(func.min(FeatureData.trade_date)).filter(
        FeatureData.ts_code == ts_code,
        FeatureData.feature_version == version,
    ).scalar()

    max_date = db.query(func.max(FeatureData.trade_date)).filter(
        FeatureData.ts_code == ts_code,
        FeatureData.feature_version == version,
    ).scalar()

    return ResponseBase(data={
        "ts_code": ts_code,
        "version": version,
        "count": count or 0,
        "min_date": min_date,
        "max_date": max_date,
        "feature_count": len(get_feature_columns()),
    })
