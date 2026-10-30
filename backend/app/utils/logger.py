import sys
from loguru import logger
from app.config import LOG_DIR

logger.remove()

log_format = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)

logger.add(sys.stdout, format=log_format, level="INFO", colorize=True)

logger.add(
    LOG_DIR / "app_{time:YYYY-MM-DD}.log",
    format=log_format,
    level="DEBUG",
    rotation="00:00",
    retention="30 days",
    compression="zip",
    encoding="utf-8",
)

logger.add(
    LOG_DIR / "error_{time:YYYY-MM-DD}.log",
    format=log_format,
    level="ERROR",
    rotation="00:00",
    retention="60 days",
    compression="zip",
    encoding="utf-8",
)

logger.add(
    LOG_DIR / "collect_{time:YYYY-MM-DD}.log",
    format=log_format,
    level="DEBUG",
    rotation="00:00",
    retention="30 days",
    filter=lambda record: "collect" in record["extra"].get("module", ""),
    encoding="utf-8",
)

logger.add(
    LOG_DIR / "train_{time:YYYY-MM-DD}.log",
    format=log_format,
    level="DEBUG",
    rotation="00:00",
    retention="30 days",
    filter=lambda record: "train" in record["extra"].get("module", ""),
    encoding="utf-8",
)


def get_logger(module_name: str = ""):
    return logger.bind(module=module_name)
