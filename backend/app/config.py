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

    # LLM providers, tried in order: Azure OpenAI -> OpenAI -> Gemini -> deterministic grounded generator.
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_key: Optional[str] = None
    azure_openai_deployment: str = "gpt-4o-mini"
    azure_openai_api_version: str = "2024-06-01"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-flash"

    # When true, sentence-transformers models are used if the package is installed.
    use_transformer_models: bool = True
    # Directory holding an exported MiniLM `model.onnx` + `vocab.txt` for torch-free semantic embeddings.
    onnx_model_dir: Optional[Path] = None
    graph_path: Path = DEFAULT_GRAPH_PATH
    ops_db_path: Path = DATA_DIR / "nexus_ops.db"
    raw_pdf_dir: Path = RAW_PDF_DIR
    cors_origins: List[str] = ["*"]
    http_timeout_seconds: float = 15.0

    # Public regulatory data APIs (keys optional; they only raise rate limits).
    openfda_api_key: Optional[str] = None
    ncbi_api_key: Optional[str] = None

    # Access control. With require_api_key=false the API is open (local demo) and the role comes from X-Nexus-Role.
    require_api_key: bool = False
    bootstrap_admin_key: Optional[str] = None
    entra_tenant_id: Optional[str] = None
    entra_audience: Optional[str] = None

    # Observability: OpenTelemetry spans are emitted when an OTLP endpoint is configured.
    otel_exporter_otlp_endpoint: Optional[str] = None
    min_answer_confidence: float = 0.35
    auto_refresh_hours: float = 0.0

    @property
    def llm_mode(self) -> str:
        if self.azure_openai_endpoint and self.azure_openai_api_key:
            return "azure-openai"
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
    settings.ops_db_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
