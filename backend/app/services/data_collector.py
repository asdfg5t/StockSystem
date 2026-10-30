import time
import tushare as ts
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.config import settings, DATA_DIR
from app.models.db_models import StockBasic, StockDaily, CollectTask, CollectLog
from app.utils.logger import get_logger

logger = get_logger("collect")


def _get_tushare_api():
    """Use the SDK default endpoint unless a custom gateway is configured."""
    if not settings.TUSHARE_TOKEN:
        raise ValueError("请先在项目根目录 .env 中配置 TUSHARE_TOKEN")
    pro = ts.pro_api(settings.TUSHARE_TOKEN)
    if settings.TUSHARE_API_URL:
        pro._DataApi__http_url = settings.TUSHARE_API_URL
    return pro


def collect_stock_basic(db: Session, task_id: int):
    """采集股票基础列表"""
    pro = _get_tushare_api()
    task = db.query(CollectTask).filter(CollectTask.id == task_id).first()
    if not task:
        return
    task.status = "running"
    task.started_at = datetime.now()
    db.commit()

    try:
        logger.info("开始采集A股股票基础列表")
        df = pro.stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,symbol,name,area,industry,market,list_date,list_status,is_hs"
        )

        if df is None or df.empty:
            raise Exception("未获取到股票基础数据")

        task.total_count = len(df)
        db.commit()

        success = 0
        for _, row in df.iterrows():
            try:
                existing = db.query(StockBasic).filter(
                    StockBasic.ts_code == row["ts_code"]
                ).first()

                if existing:
                    existing.name = row.get("name", existing.name)
                    existing.area = row.get("area", existing.area)
                    existing.industry = row.get("industry", existing.industry)
                    existing.market = row.get("market", existing.market)
                    existing.list_date = row.get("list_date", existing.list_date)
                    existing.list_status = row.get("list_status", existing.list_status)
                    existing.is_hs = row.get("is_hs", existing.is_hs)
                else:
                    stock = StockBasic(
                        ts_code=row["ts_code"],
                        symbol=row.get("symbol", ""),
                        name=row.get("name", ""),
                        area=row.get("area"),
                        industry=row.get("industry"),
                        market=row.get("market"),
                        list_date=row.get("list_date"),
                        list_status=row.get("list_status", "L"),
                        is_hs=row.get("is_hs"),
                    )
                    db.add(stock)

                success += 1
            except Exception as e:
                logger.error(f"保存股票 {row.get('ts_code')} 失败: {e}")
                continue

        db.commit()

        txt_path = DATA_DIR / "stock_basic.txt"
        df.to_csv(str(txt_path), sep="\t", index=False, encoding="utf-8")
        logger.info(f"股票基础数据已保存到 {txt_path}")

        task.success_count = success
        task.status = "completed"
        task.progress = 100
        task.finished_at = datetime.now()
        db.commit()

        _log_collect(db, task_id, None, "success", f"成功采集 {success} 只股票基础信息")
        logger.info(f"股票基础列表采集完成, 共 {success} 只")

    except Exception as e:
        db.rollback()
        logger.error(f"采集股票基础列表失败: {e}")
        task.status = "failed"
        task.error_msg = str(e)
        task.finished_at = datetime.now()
        db.commit()
        _log_collect(db, task_id, None, "failed", str(e))


def collect_daily_data(db: Session, task_id: int):
    """采集日线行情数据（支持断点续采、分批采集、异常重试）"""
    pro = _get_tushare_api()
    task = db.query(CollectTask).filter(CollectTask.id == task_id).first()
    if not task:
        return
    task.status = "running"
    task.started_at = datetime.now()
    db.commit()

    try:
        if task.ts_code:
            stock_codes = [task.ts_code]
        else:
            stocks = db.query(StockBasic.ts_code).filter(
                StockBasic.list_status == "L"
            ).all()
            stock_codes = [s.ts_code for s in stocks]

        if not stock_codes:
            raise Exception("无可采集的股票代码，请先采集股票基础列表")

        end_date = _to_date_str(task.end_date) if task.end_date else datetime.now().strftime("%Y%m%d")
        start_date = _to_date_str(task.start_date) if task.start_date else (
            datetime.now() - timedelta(days=365 * settings.DATA_YEARS)
        ).strftime("%Y%m%d")

        task.total_count = len(stock_codes)
        db.commit()

        success_count = 0
        fail_count = 0
        batch_size = settings.COLLECT_BATCH_SIZE

        for i in range(0, len(stock_codes), batch_size):
            batch = stock_codes[i:i + batch_size]
            for code in batch:
                collected = _collect_single_stock_daily(
                    pro, db, task_id, code, start_date, end_date
                )
                if collected:
                    success_count += 1
                else:
                    fail_count += 1

                task.success_count = success_count
                task.fail_count = fail_count
                task.progress = round(
                    (success_count + fail_count) / len(stock_codes) * 100, 2
                )
                db.commit()

            if i + batch_size < len(stock_codes):
                time.sleep(1)

        task.status = "completed"
        task.finished_at = datetime.now()
        db.commit()

        logger.info(
            f"日线数据采集完成: 成功 {success_count}, 失败 {fail_count}"
        )

    except Exception as e:
        db.rollback()
        logger.error(f"采集日线数据失败: {e}")
        task.status = "failed"
        task.error_msg = str(e)
        task.finished_at = datetime.now()
        db.commit()
        _log_collect(db, task_id, None, "failed", str(e))


def _to_date_str(val) -> str:
    """将 datetime.date / datetime / 字符串统一转为 YYYYMMDD 字符串"""
    if hasattr(val, 'strftime'):
        return val.strftime("%Y%m%d")
    return str(val).replace("-", "")


def _collect_single_stock_daily(
    pro, db: Session, task_id: int, ts_code: str,
    start_date: str, end_date: str
) -> bool:
    """采集单只股票日线（含断点续采）"""
    # 防御：上游可能传 int / date，统一为 YYYYMMDD 字符串，避免 str 与 int 比较报错
    start_date = _to_date_str(start_date)
    end_date = _to_date_str(end_date)
    actual_start = start_date

    latest = db.query(StockDaily.trade_date).filter(
        StockDaily.ts_code == ts_code
    ).order_by(StockDaily.trade_date.desc()).first()

    if latest:
        latest_str = _to_date_str(latest.trade_date)
        if latest_str >= start_date:
            actual_start = (
                datetime.strptime(latest_str, "%Y%m%d") + timedelta(days=1)
            ).strftime("%Y%m%d")
            if actual_start > end_date:
                logger.debug(f"{ts_code} 数据已是最新，跳过")
                _log_collect(db, task_id, ts_code, "success", "数据已是最新")
                return True

    for retry in range(settings.COLLECT_RETRY):
        try:
            df = pro.daily(
                ts_code=ts_code,
                start_date=actual_start,
                end_date=end_date
            )

            if df is None or df.empty:
                logger.debug(f"{ts_code} 在 {actual_start}-{end_date} 无数据")
                _log_collect(db, task_id, ts_code, "success", "无新增数据")
                return True

            inserted = 0
            for _, row in df.iterrows():
                exists = db.query(StockDaily.id).filter(
                    StockDaily.ts_code == ts_code,
                    StockDaily.trade_date == row["trade_date"]
                ).first()
                if exists:
                    continue

                daily = StockDaily(
                    ts_code=row["ts_code"],
                    trade_date=row["trade_date"],
                    open=row.get("open"),
                    high=row.get("high"),
                    low=row.get("low"),
                    close=row.get("close"),
                    pre_close=row.get("pre_close"),
                    change=row.get("change"),
                    pct_chg=row.get("pct_chg"),
                    vol=row.get("vol"),
                    amount=row.get("amount"),
                )
                db.add(daily)
                inserted += 1

            db.commit()

            txt_dir = DATA_DIR / "daily"
            txt_dir.mkdir(parents=True, exist_ok=True)
            txt_path = txt_dir / f"{ts_code.replace('.', '_')}.txt"
            # 防御：Tushare 返回的 trade_date / ts_code 是字符串，但 pd.read_csv 会把全数字
            # 字符串列推断为 int，concat 后混合类型导致 sort_values 抛
            #   "'<' not supported between instances of 'str' and 'int'"。
            # 这里强制以 str 读取 + 写出前再统一一次。
            df_to_write = df.copy()
            df_to_write["ts_code"] = df_to_write["ts_code"].astype(str)
            df_to_write["trade_date"] = df_to_write["trade_date"].astype(str)
            if txt_path.exists():
                old_df = pd.read_csv(
                    str(txt_path), sep="\t",
                    dtype={"ts_code": str, "trade_date": str},
                )
                combined = pd.concat([old_df, df_to_write], ignore_index=True)
                combined["ts_code"] = combined["ts_code"].astype(str)
                combined["trade_date"] = combined["trade_date"].astype(str)
                combined.drop_duplicates(
                    subset=["ts_code", "trade_date"], keep="last", inplace=True
                )
                combined.sort_values("trade_date", inplace=True)
                combined.to_csv(str(txt_path), sep="\t", index=False, encoding="utf-8")
            else:
                df_to_write.sort_values("trade_date", inplace=True)
                df_to_write.to_csv(str(txt_path), sep="\t", index=False, encoding="utf-8")

            _log_collect(
                db, task_id, ts_code, "success",
                f"新增 {inserted} 条日线数据"
            )
            logger.info(f"{ts_code} 采集完成, 新增 {inserted} 条")
            return True

        except Exception as e:
            db.rollback()
            logger.warning(
                f"{ts_code} 采集失败 (第{retry+1}次): {e}"
            )
            _log_collect(
                db, task_id, ts_code, "retry",
                f"第{retry+1}次重试: {e}", retry_count=retry + 1
            )
            time.sleep(settings.COLLECT_RETRY_INTERVAL)

    _log_collect(db, task_id, ts_code, "failed", f"重试 {settings.COLLECT_RETRY} 次后失败")
    logger.error(f"{ts_code} 采集最终失败")
    return False


def _log_collect(
    db: Session, task_id: int, ts_code: str,
    status: str, message: str, retry_count: int = 0
):
    log = CollectLog(
        task_id=task_id,
        ts_code=ts_code,
        status=status,
        message=message,
        retry_count=retry_count,
    )
    db.add(log)
    db.commit()


def get_collect_progress(db: Session, task_id: int) -> dict:
    task = db.query(CollectTask).filter(CollectTask.id == task_id).first()
    if not task:
        return {}
    return {
        "id": task.id,
        "status": task.status,
        "total": task.total_count,
        "success": task.success_count,
        "fail": task.fail_count,
        "progress": float(task.progress),
    }
