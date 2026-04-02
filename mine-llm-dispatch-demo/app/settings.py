from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    timezone: str = Field(default="Asia/Shanghai", alias="TIMEZONE")
    snapshot_window_minutes: int = Field(default=30, alias="SNAPSHOT_WINDOW_MINUTES")
    vector_store: str = Field(default="chroma", alias="VECTOR_STORE")
    vector_store_path: Path = Field(default=Path("data/vector/chroma"), alias="VECTOR_STORE_PATH")
    audit_log_path: Path = Field(default=Path("data/audit/audit.jsonl"), alias="AUDIT_LOG_PATH")
    knowledge_base_path: Path = Field(default=Path("docs/knowledge_base"), alias="KNOWLEDGE_BASE_PATH")
    rules_path: Path = Field(default=Path("app/rules/sample_rules.yaml"), alias="RULES_PATH")
    llm_provider: str = Field(default="mock", alias="LLM_PROVIDER")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_auth_token: str | None = Field(default=None, alias="ANTHROPIC_AUTH_TOKEN")
    anthropic_model: str = Field(default="claude-opus-4-6", alias="ANTHROPIC_MODEL")
    anthropic_base_url: str | None = Field(default=None, alias="ANTHROPIC_BASE_URL")
    anthropic_max_tokens: int = Field(default=1500, alias="ANTHROPIC_MAX_TOKENS")
    anthropic_timeout_seconds: float = Field(default=20.0, alias="ANTHROPIC_TIMEOUT_SECONDS")
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def resolve_path(self, path: Path) -> Path:
        return path if path.is_absolute() else self.project_root / path

    @property
    def resolved_llm_api_key(self) -> str | None:
        return self.anthropic_api_key or self.anthropic_auth_token or self.llm_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
