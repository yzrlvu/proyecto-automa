"""Configuración central del sistema — Sistema Automatizado de Gestión de Citas (Grupo 10)."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_name: str = "citas-clinica"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    # --- LLM (Groq) ---
    groq_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1024

    # --- Base de datos ---
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/citas"

    # --- RAG ---
    chroma_persist_dir: str = "./chroma_db"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    rag_top_k: int = 4

    # --- Observabilidad (LangSmith) ---
    langsmith_tracing: bool = True
    langsmith_api_key: str = ""
    langsmith_project: str = "citas-clinica-grupo10"

    # --- Telegram ---
    telegram_bot_token: str = ""

    # --- Email fallback ---
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # --- Scheduler ---
    reminder_hours_before: int = 24
    slot_hold_timeout_minutes: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
