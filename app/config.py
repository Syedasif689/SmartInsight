import os
from pathlib import Path


def env_value(name: str, default=None):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value


def env_int(name: str, default: int) -> int:
    value = env_value(name)
    if value is None:
        return default
    return int(value)


def env_bool(name: str, default: bool) -> bool:
    value = env_value(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


class BaseConfig:
    MAIL_SERVER = env_value("MAIL_SERVER", "smtp.sendgrid.net")
    MAIL_PORT = env_int("MAIL_PORT", 587)
    MAIL_USE_TLS = env_bool("MAIL_USE_TLS", True)
    MAIL_TIMEOUT = env_int("MAIL_TIMEOUT", 10)

    MAIL_USERNAME = env_value("MAIL_USERNAME")
    MAIL_PASSWORD = env_value("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = env_value("MAIL_DEFAULT_SENDER", MAIL_USERNAME)
    SECRET_KEY = env_value("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = env_value(
        "DATABASE_URL",
        f"sqlite:///{Path.cwd() / 'smartinsight.db'}",
    )
    JSON_SORT_KEYS = False
    MAX_UPLOAD_MB = env_int("MAX_UPLOAD_MB", 200)
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    FAST_ANALYSIS_ROW_LIMIT = env_int("FAST_ANALYSIS_ROW_LIMIT", 10000)
    COLUMN_SCAN_ROW_LIMIT = env_int("COLUMN_SCAN_ROW_LIMIT", 1000)
    DUPLICATE_CHECK_MAX_MB = env_int("DUPLICATE_CHECK_MAX_MB", 5)
    UPLOAD_FOLDER = env_value(
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
