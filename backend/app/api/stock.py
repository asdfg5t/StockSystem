from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.database import get_db
from app.models.db_models import StockBasic, StockDaily
from app.models.schemas import ResponseBase, PageResponse

router = APIRouter(prefix="/stock", tags=["股票数据"])


@router.get("/list")
def get_stock_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query("", description="搜索关键词"),
    industry: str = Query("", description="行业筛选"),
    db: Session = Depends(get_db),
):
    query = db.query(StockBasic).filter(StockBasic.list_status == "L")
    if keyword:
        query = query.filter(
            or_(
                StockBasic.ts_code.like(f"%{keyword}%"),
                StockBasic.name.like(f"%{keyword}%"),
                StockBasic.symbol.like(f"%{keyword}%"),
            )
        )
    if industry:
        query = query.filter(StockBasic.industry == industry)

    total = query.count()
    items = query.order_by(StockBasic.ts_code).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return PageResponse(
        data=[_stock_to_dict(s) for s in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/industries")
def get_industries(db: Session = Depends(get_db)):
    industries = db.query(StockBasic.industry).filter(
        StockBasic.industry.isnot(None)
    ).distinct().all()
    return ResponseBase(data=[i[0] for i in industries if i[0]])


@router.get("/detail/{ts_code}")
def get_stock_detail(ts_code: str, db: Session = Depends(get_db)):
    stock = db.query(StockBasic).filter(StockBasic.ts_code == ts_code).first()
    if not stock:
        return ResponseBase(code=404, message="股票不存在")

    daily_count = db.query(func.count(StockDaily.id)).filter(
        StockDaily.ts_code == ts_code
    ).scalar()

    latest = db.query(StockDaily).filter(
        StockDaily.ts_code == ts_code
    ).order_by(StockDaily.trade_date.desc()).first()

    return ResponseBase(data={
        "basic": _stock_to_dict(stock),
        "daily_count": daily_count,
        "latest_daily": _daily_to_dict(latest) if latest else None,
    })


@router.get("/daily/{ts_code}")
def get_daily_data(
    ts_code: str,
    start_date: str = Query("", description="开始日期"),
    end_date: str = Query("", description="结束日期"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(StockDaily).filter(StockDaily.ts_code == ts_code)
    if start_date:
        query = query.filter(StockDaily.trade_date >= start_date)
    if end_date:
        query = query.filter(StockDaily.trade_date <= end_date)

    total = query.count()
    items = query.order_by(StockDaily.trade_date.asc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return PageResponse(
        data=[_daily_to_dict(d) for d in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/kline/{ts_code}")
def get_kline_data(
    ts_code: str,
    start_date: str = Query(""),
    end_date: str = Query(""),
    db: Session = Depends(get_db),
):
    query = db.query(StockDaily).filter(StockDaily.ts_code == ts_code)
    if start_date:
        query = query.filter(StockDaily.trade_date >= start_date)
    if end_date:
        query = query.filter(StockDaily.trade_date <= end_date)

    items = query.order_by(StockDaily.trade_date.asc()).all()
    kline = []
    for d in items:
        kline.append({
            "date": d.trade_date,
            "open": float(d.open) if d.open else 0,
            "close": float(d.close) if d.close else 0,
            "high": float(d.high) if d.high else 0,
            "low": float(d.low) if d.low else 0,
            "vol": float(d.vol) if d.vol else 0,
            "amount": float(d.amount) if d.amount else 0,
        })
    return ResponseBase(data=kline)


def _stock_to_dict(s):
    return {
        "id": s.id, "ts_code": s.ts_code, "symbol": s.symbol,
        "name": s.name, "area": s.area, "industry": s.industry,
        "market": s.market, "list_date": s.list_date,
        "list_status": s.list_status,
    }


def _daily_to_dict(d):
    return {
        "id": d.id, "ts_code": d.ts_code, "trade_date": d.trade_date,
        "open": float(d.open) if d.open else None,
        "high": float(d.high) if d.high else None,
        "low": float(d.low) if d.low else None,
        "close": float(d.close) if d.close else None,
        "pre_close": float(d.pre_close) if d.pre_close else None,
        "change": float(d.change) if d.change else None,
        "pct_chg": float(d.pct_chg) if d.pct_chg else None,
        "vol": float(d.vol) if d.vol else None,
        "amount": float(d.amount) if d.amount else None,
    }
