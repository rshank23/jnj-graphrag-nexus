"""Environment and path settings for the J&J GraphRAG Nexus backend."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
RAW_PDF_DIR = DATA_DIR / "raw_pdfs"
DEFAULT_GRAPH_PATH = DATA_DIR / "jnj_graph.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "J&J GraphRAG Nexus"
    neo4j_uri: Optional[str] = None
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    neo4j_database: str = "neo4j"

    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-flash"

    # When true, sentence-transformers models are used if the package is installed.
    use_transformer_models: bool = True
    graph_path: Path = DEFAULT_GRAPH_PATH
    raw_pdf_dir: Path = RAW_PDF_DIR
    cors_origins: List[str] = ["*"]
    http_timeout_seconds: float = 15.0

    @property
    def llm_mode(self) -> str:
        if self.openai_api_key:
            return "openai"
        if self.gemini_api_key:
            return "gemini"
        return "local-deterministic"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.graph_path.parent.mkdir(parents=True, exist_ok=True)
    settings.raw_pdf_dir.mkdir(parents=True, exist_ok=True)
    return settings
