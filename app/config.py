import os
from pathlib import Path


class BaseConfig:
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True") == "True"

    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    JSON_SORT_KEYS = False
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "200"))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    FAST_ANALYSIS_ROW_LIMIT = int(
        os.getenv("FAST_ANALYSIS_ROW_LIMIT", "10000")
    )
    COLUMN_SCAN_ROW_LIMIT = int(
        os.getenv("COLUMN_SCAN_ROW_LIMIT", "1000")
    )
    DUPLICATE_CHECK_MAX_MB = int(
        os.getenv("DUPLICATE_CHECK_MAX_MB", "5")
    )
    UPLOAD_FOLDER = os.getenv(
        "UPLOAD_FOLDER",
        str(Path.cwd() / "uploads"),
    )
    ALLOWED_EXTENSIONS = {"csv", "xls", "xlsx"}


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True


class ProductionConfig(BaseConfig):
    DEBUG = False


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
