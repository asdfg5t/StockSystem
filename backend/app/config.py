import os
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")
DATA_DIR = BASE_DIR / "data" / "raw"
MODEL_DIR = BASE_DIR / "saved_models"
LOG_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


class Settings:
    PROJECT_NAME: str = "基于深度学习的股票预测系统"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"

    DB_HOST: str = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "stock_prediction")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{quote_plus(self.DB_USER)}:{quote_plus(self.DB_PASSWORD)}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?charset=utf8mb4"
        )

    TUSHARE_TOKEN: str = os.getenv("TUSHARE_TOKEN", "")
    TUSHARE_API_URL: str = os.getenv("TUSHARE_API_URL", "")

    DEFAULT_LOOKBACK: int = 60
    DEFAULT_EPOCHS: int = 100
    DEFAULT_BATCH_SIZE: int = 32
    DEFAULT_LR: float = 0.001

    COLLECT_BATCH_SIZE: int = 50
    COLLECT_RETRY: int = 3
    COLLECT_RETRY_INTERVAL: int = 5
    DATA_YEARS: int = 3

    CORS_ORIGINS: list = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
