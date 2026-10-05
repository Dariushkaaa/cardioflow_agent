from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения (читаются из переменных окружения и файла .env)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Подключение к БД и безопасность
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/cardioflow_db"
    SECRET_KEY: str = "your_jwt_secret_key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 15-30 минут по спецификации

    # Agent Service (проксирование реплик пациента)
    AGENT_SERVICE_URL: str = "http://localhost:8001/api/v1/agent/process"
    AGENT_TIMEOUT_SECONDS: float = 20.0

    # Время и планировщик
    TIMEZONE: str = "Europe/Moscow"
    SESSION_DEADLINE_HOURS: int = 2
    DAILY_SUMMARY_HOUR: int = 22
    DAILY_SUMMARY_MINUTE: int = 0
    REMINDER_CHECK_MINUTES: int = 5
    LOST_AFTER_MISSED_SESSIONS: int = 4

    # Флаги запуска
    AUTO_CREATE_TABLES: bool = True
    SEED_DEMO_DATA: bool = True
    ENABLE_DEV_TOKEN: bool = True
    ENABLE_SCHEDULER: bool = True


settings = Settings()
