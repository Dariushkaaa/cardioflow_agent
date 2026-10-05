from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # --- LLM (GigaChat по умолчанию; любой OpenAI-совместимый API тоже подходит) ---
    # Пустой LLM_API_KEY = режим правил: агент работает без внешних вызовов.
    llm_api_key: str = ""
    llm_model_name: str = "GigaChat"
    llm_base_url: str = "https://api.giga.chat/v1"
    # auto | gigachat | openai. auto: GigaChat, если в адресе/модели есть giga/sber.
    llm_provider: str = "auto"
    # OAuth GigaChat: POST {llm_auth_url} с Basic <ключ авторизации> -> access_token (живет ~30 минут)
    llm_auth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    # GIGACHAT_API_PERS (физлица), GIGACHAT_API_B2B или GIGACHAT_API_CORP
    llm_scope: str = "GIGACHAT_API_PERS"
    # Сертификаты Сбера подписаны российским УЦ Минцифры, которого нет в стандартном хранилище.
    # false = не проверять сертификат (по умолчанию, чтобы работало из коробки);
    # путь к .pem/.crt = проверять по своему корневому сертификату (рекомендуется для продакшена).
    llm_verify_ssl: bool = False
    llm_ca_bundle: str = ""
    llm_timeout: float = 30.0

    backend_api_url: str = "http://localhost:8000/api/v1"
    request_timeout: float = 15.0
    # Каталог с утвержденными .txt материалами для RAG
    rag_docs_dir: str = str(BASE_DIR / "knowledge")
    # Часовой пояс для показа времени слотов пациенту
    timezone: str = "Europe/Moscow"
    app_name: str = "CardioFlow Agent Service"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
