from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from songwriter.seeds import DB_PATH as DEFAULT_DB_PATH


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SONGWRITER_", env_file=".env", extra="ignore")

    db_path: Path = DEFAULT_DB_PATH
    songs_dir: Path = Path.home() / "Songwriter" / "songs"
    cors_origins: list[str] = ["http://localhost:3737", "http://localhost:3000"]

    # Cerebras — fast, cheap; used for GENERAL fallback
    cerebras_model_id: str = "qwen-3-235b-a22b-instruct-2507"
    cerebras_key_path: str = "~/.cerebras_api_key"

    # Google Gemini Flash — used for VALIDATE / SUNO (~4x cheaper than Cerebras)
    gemini_model_id: str = "gemini-2.5-flash"
    gemini_key_path: str = "~/.gemini_api_key"

    # Anthropic API — used for DRAFT (Sonnet) and optionally REPAIR (Haiku)
    anthropic_sonnet_id: str = "claude-sonnet-4-6"
    anthropic_haiku_id: str = "claude-haiku-4-5-20251001"
    anthropic_key_path: str = "~/.maxrpg_api_key"

    # Claude CLI (fallback when Anthropic key absent)
    claude_cli: str = "claude"
    llm_timeout_s: int = 60


def get_settings() -> Settings:
    return Settings()
