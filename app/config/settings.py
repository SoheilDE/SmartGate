from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Fast tier
    fast_model: str = "gpt-3.5-turbo"
    fast_model_base_url: str = "https://api.openai.com/v1"
    fast_model_api_key: str = ""

    # Powerful tier
    powerful_model: str = "gpt-4"
    powerful_model_base_url: str = "https://api.openai.com/v1"
    powerful_model_api_key: str = ""

    # Routing
    complexity_threshold: float = 0.6

    # Semantic cache
    cache_similarity_threshold: float = 0.92
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "smartgate_cache"

    # Telemetry
    metrics_db_path: str = "./metrics.db"


settings = Settings()
