"""Central configuration via pydantic-settings.

All settings can be overridden by environment variables prefixed with ``ACHILLES_``
or by a local ``.env`` file. Paths are resolved relative to the project root.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = two levels up from this file (app/config/settings.py -> root)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve(p: str | Path) -> Path:
    """Resolve a path relative to PROJECT_ROOT unless it is already absolute."""
    path = Path(p)
    return path if path.is_absolute() else (PROJECT_ROOT / path)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ACHILLES_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Local LLM ---
    ollama_host: str = "http://localhost:11434"
    llm_model: str = "qwen2.5-coder:7b"
    embed_model: str = "nomic-embed-text"

    # --- Storage ---
    sqlite_path: Path = Field(default=Path("storage/sqlite/achilles_trader_ai.db"))
    chroma_path: Path = Field(default=Path("vector_db/chroma"))

    # --- RAG ---
    rag_top_k: int = 6
    chunk_size: int = 1200
    chunk_overlap: int = 200

    # --- Trading ---
    default_market: str = "XAUUSD"
    default_timeframe: str = "15m"

    # --- Behavior ---
    allow_fake_embeddings: bool = True
    log_level: str = "INFO"

    # --- Web (FastAPI) ---
    # Güvenlik: varsayılan olarak SADECE localhost'a bağlanır (dışarı açılmaz).
    web_host: str = "127.0.0.1"
    web_port: int = 8765
    # Boşsa kimlik doğrulama kapalıdır (yalnız localhost güvenli sayılır).
    # Sunucuyu ağa açacaksan MUTLAKA güçlü bir token ata.
    api_token: str = ""
    # CORS: yalnız bu kökenlere izin verilir (frontend aynı origin'den sunulur).
    cors_origins: str = "http://127.0.0.1:8765,http://localhost:8765"
    # PDF upload üst sınırı (MB).
    max_upload_mb: int = 50
    # Basit hız sınırı: IP başına dakikadaki istek.
    rate_limit_per_min: int = 120

    # --- Derived dirs (not env-configurable) ---
    @property
    def root(self) -> Path:
        return PROJECT_ROOT

    @property
    def sqlite_file(self) -> Path:
        return _resolve(self.sqlite_path)

    @property
    def chroma_dir(self) -> Path:
        return _resolve(self.chroma_path)

    @property
    def raw_pdf_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "papers" / "raw_pdf"

    @property
    def extracted_text_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "papers" / "extracted_text"

    @property
    def metadata_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "papers" / "metadata"

    @property
    def jsonl_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "training" / "jsonl"

    @property
    def market_raw_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "market" / "raw"

    @property
    def reports_dir(self) -> Path:
        return PROJECT_ROOT / "reports"

    @property
    def adapters_dir(self) -> Path:
        return PROJECT_ROOT / "models" / "adapters"

    @property
    def prompts_dir(self) -> Path:
        return PROJECT_ROOT / "app" / "prompts"

    def ensure_dirs(self) -> None:
        """Create all runtime directories that must exist."""
        for d in (
            self.sqlite_file.parent,
            self.chroma_dir,
            self.raw_pdf_dir,
            self.extracted_text_dir,
            self.metadata_dir,
            self.jsonl_dir,
            self.market_raw_dir,
            self.adapters_dir,
            self.reports_dir / "papers",
            self.reports_dir / "training",
            self.reports_dir / "backtests",
            self.reports_dir / "evals",
        ):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def configure_logging(level: str | None = None) -> None:
    settings = get_settings()
    logging.basicConfig(
        level=(level or settings.log_level).upper(),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
