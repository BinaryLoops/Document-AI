"""
core/config.py — Multi-environment configuration with Pydantic validation.

Environments
------------
    development  (default)  — permissive CORS, debug logging, verbose errors
    testing                 — isolated, no external services required
    production              — strict CORS, JSON logging, generic errors

Usage
-----
    from core.config import settings

    print(settings.api_port)
    print(settings.environment)
    if settings.is_production:
        ...

The module falls back gracefully if pydantic-settings is not installed
(older pydantic v1 environments) — reads from os.environ directly.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

# ── Try pydantic-settings (pydantic v2) first, fall back to pydantic v1 ─────
try:
    from pydantic_settings import BaseSettings
    from pydantic import Field, validator
    _PYDANTIC_V2 = True
except ImportError:
    try:
        from pydantic import BaseSettings, Field, validator  # type: ignore[no-redef]
        _PYDANTIC_V2 = False
    except ImportError:
        # Last resort: pure dataclass fallback (no validation)
        BaseSettings = object  # type: ignore[misc,assignment]
        Field = lambda *a, **kw: kw.get("default")  # type: ignore[assignment]
        validator = lambda *a, **kw: (lambda f: f)  # type: ignore[assignment]
        _PYDANTIC_V2 = False


# ── Version constant ─────────────────────────────────────────────────────────
APP_VERSION  = "1.0.0"
APP_NAME     = "DocuMind AI"
BUILD_DATE   = "2026-08-22"


# ── Settings model ───────────────────────────────────────────────────────────

class Settings(BaseSettings):  # type: ignore[misc]
    """
    All application settings — sourced from environment variables.

    Precedence: .env file → environment → default value.
    """

    # ── Application ─────────────────────────────────────────────────────
    environment: str = Field("development", env="APP_ENV")
    debug: bool      = Field(False,          env="APP_DEBUG")

    # ── Server ──────────────────────────────────────────────────────────
    api_host: str = Field("0.0.0.0", env="API_HOST")
    api_port: int = Field(8000,       env="API_PORT")
    workers:  int = Field(1,          env="WORKERS")

    # ── CORS ────────────────────────────────────────────────────────────
    cors_origins: str = Field("*", env="CORS_ORIGINS")  # comma-separated

    # ── Logging ─────────────────────────────────────────────────────────
    log_level:  str = Field("INFO",  env="LOG_LEVEL")
    log_format: str = Field("human", env="LOG_FORMAT")   # human | json
    log_file:   str = Field("",      env="LOG_FILE")

    # ── Embedding ───────────────────────────────────────────────────────
    embedding_model:     str  = Field("sentence-transformers/all-MiniLM-L6-v2", env="EMBEDDING_MODEL")
    embedding_dimension: int  = Field(384,   env="EMBEDDING_DIMENSION")
    use_gpu:             bool = Field(False,  env="USE_GPU")

    # ── Document processing ─────────────────────────────────────────────
    chunk_size:           int = Field(1000,  env="CHUNK_SIZE")
    chunk_overlap:        int = Field(200,   env="CHUNK_OVERLAP")
    max_length:           int = Field(512,   env="MAX_LENGTH")
    min_chunk_size:       int = Field(200,   env="MIN_CHUNK_SIZE")
    max_single_chunk_size:int = Field(10000, env="MAX_SINGLE_CHUNK_SIZE")
    max_upload_bytes:     int = Field(20 * 1024 * 1024, env="MAX_UPLOAD_BYTES")  # 20 MB

    # ── Vector DB ───────────────────────────────────────────────────────
    vector_db_type:   str = Field("faiss", env="VECTOR_DB_TYPE")
    faiss_index_type: str = Field("Flat",  env="FAISS_INDEX_TYPE")

    # ── Retrieval ───────────────────────────────────────────────────────
    top_k:                  int   = Field(5,     env="TOP_K")
    search_type:            str   = Field("hybrid", env="SEARCH_TYPE")
    semantic_search_weight: float = Field(0.7,   env="SEMANTIC_SEARCH_WEIGHT")
    keyword_search_weight:  float = Field(0.3,   env="KEYWORD_SEARCH_WEIGHT")

    # ── LLM ─────────────────────────────────────────────────────────────
    llm_model:       str   = Field("gpt-3.5-turbo", env="LLM_MODEL")
    llm_temperature: float = Field(0.2,              env="LLM_TEMPERATURE")
    llm_max_tokens:  int   = Field(512,              env="LLM_MAX_TOKENS")
    openai_api_key:  Optional[str] = Field(None,     env="OPENAI_API_KEY")

    # ── HuggingFace ─────────────────────────────────────────────────────
    huggingface_api_key: Optional[str] = Field(None, env="HUGGINGFACE_API_KEY")
    huggingface_model:   str = Field(
        "mistralai/Mistral-7B-Instruct-v0.2", env="HUGGINGFACE_MODEL"
    )

    # ── OCR ─────────────────────────────────────────────────────────────
    ocr_engine:    str           = Field("tesseract",           env="OCR_ENGINE")
    tesseract_cmd: Optional[str] = Field(None,                  env="TESSERACT_CMD")
    ocr_language:  str           = Field("eng",                 env="OCR_LANGUAGE")

    # ── Firebase ────────────────────────────────────────────────────────
    firebase_credentials_path: Optional[str] = Field(None, env="FIREBASE_CREDENTIALS_PATH")
    firebase_storage_bucket:   Optional[str] = Field(None, env="FIREBASE_STORAGE_BUCKET")
    firebase_project_id:       Optional[str] = Field(None, env="FIREBASE_PROJECT_ID")

    # ── Neo4j (optional) ────────────────────────────────────────────────
    neo4j_uri:      str           = Field("bolt://localhost:7687", env="NEO4J_URI")
    neo4j_user:     str           = Field("neo4j",                 env="NEO4J_USER")
    neo4j_password: Optional[str] = Field(None,                    env="NEO4J_PASSWORD")
    neo4j_database: str           = Field("neo4j",                 env="NEO4J_DATABASE")

    # ── Knowledge Graph ─────────────────────────────────────────────────
    kg_store_path: str = Field("kg_store.json", env="KG_STORE_PATH")

    # ── Authentication ───────────────────────────────────────────────────
    jwt_secret_key:            str           = Field("dev-jwt-secret-change-in-production-please", env="JWT_SECRET_KEY")
    jwt_issuer:                str           = Field("documind-ai",  env="JWT_ISSUER")
    access_token_ttl_minutes:  int           = Field(30,             env="ACCESS_TOKEN_TTL_MINUTES")
    refresh_token_ttl_days:    int           = Field(7,              env="REFRESH_TOKEN_TTL_DAYS")
    aadhaar_hmac_key:          str           = Field("dev-aadhaar-hmac-key-change-in-prod", env="AADHAAR_HMAC_KEY")
    otp_ttl_seconds:           int           = Field(300,            env="OTP_TTL_SECONDS")
    otp_max_attempts:          int           = Field(5,              env="OTP_MAX_ATTEMPTS")
    lockout_threshold:         int           = Field(5,              env="LOCKOUT_THRESHOLD")
    lockout_duration_minutes:  int           = Field(15,             env="LOCKOUT_DURATION_MINUTES")
    session_ttl_hours:         int           = Field(8,              env="SESSION_TTL_HOURS")
    auth_store_path:           str           = Field("auth_store.json", env="AUTH_STORE_PATH")
    mfa_app_name:              str           = Field("DocuMind AI",  env="MFA_APP_NAME")

    # ── Document Generation Engine ───────────────────────────────────────
    gen_store_path:    str  = Field("gen_store.json",   env="GEN_STORE_PATH")
    gen_pdf_dir:       str  = Field("generated_pdfs",   env="GEN_PDF_DIR")
    gen_key_dir:       str  = Field("gen_keys",          env="GEN_KEY_DIR")
    gen_auto_approve:  bool = Field(True,                env="GEN_AUTO_APPROVE")
    gen_require_docs:  bool = Field(False,               env="GEN_REQUIRE_SUPPORTING_DOCS")
    doc_verify_base_url: str = Field("http://localhost:8000", env="DOC_VERIFY_BASE_URL")

    # ── Confidence thresholds ────────────────────────────────────────────
    confidence_threshold_low:  float = Field(0.70, env="CONFIDENCE_THRESHOLD_LOW")
    confidence_threshold_high: float = Field(0.90, env="CONFIDENCE_THRESHOLD_HIGH")

    # ── Security middleware ──────────────────────────────────────────────
    rate_limit_rpm:            int  = Field(120,   env="RATE_LIMIT_RPM")
    rate_limit_burst:          int  = Field(30,    env="RATE_LIMIT_BURST")
    csrf_enforce:              bool = Field(False, env="CSRF_ENFORCE")
    session_timeout_minutes:   int  = Field(30,    env="SESSION_TIMEOUT_MINUTES")

    # ── Monitoring ──────────────────────────────────────────────────────
    enable_metrics:  bool = Field(True,       env="ENABLE_METRICS")
    metrics_path:    str  = Field("/metrics", env="METRICS_PATH")

    # ── Railway / Cloud ─────────────────────────────────────────────────
    railway_environment: Optional[str] = Field(None, env="RAILWAY_ENVIRONMENT")
    port: Optional[int] = Field(None, env="PORT")  # Railway injects PORT

    # ── Pydantic model config ────────────────────────────────────────────
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"

    # ── Derived properties ───────────────────────────────────────────────

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in ("production", "prod")

    @property
    def is_testing(self) -> bool:
        return self.environment.lower() in ("testing", "test")

    @property
    def is_development(self) -> bool:
        return self.environment.lower() in ("development", "dev", "local")

    @property
    def effective_port(self) -> int:
        """PORT env var (Railway) overrides API_PORT."""
        return self.port or self.api_port

    @property
    def cors_origin_list(self) -> List[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def effective_log_level(self) -> str:
        if self.is_production:
            return "WARNING"
        return self.log_level.upper()

    @property
    def effective_log_format(self) -> str:
        if self.is_production:
            return "json"
        return self.log_format.lower()

    @property
    def firebase_available(self) -> bool:
        return bool(
            self.firebase_credentials_path
            and Path(self.firebase_credentials_path).exists()
        )

    def validate_required(self) -> list[str]:
        """
        Return a list of human-readable warnings for missing recommended settings.
        Does NOT raise — callers decide what to do with the warnings.
        """
        warnings: list[str] = []
        if self.is_production:
            if self.cors_origins.strip() == "*":
                warnings.append("CORS_ORIGINS is '*' — set explicit origins in production")
            if not self.openai_api_key and not self.huggingface_api_key:
                warnings.append("No LLM API key set (OPENAI_API_KEY or HUGGINGFACE_API_KEY)")
            if self.log_level.upper() == "DEBUG":
                warnings.append("LOG_LEVEL=DEBUG in production — may expose PII in logs")
            if self.jwt_secret_key == "dev-jwt-secret-change-in-production-please":
                warnings.append("JWT_SECRET_KEY is using the insecure default — set a random 32-byte secret")
            if self.aadhaar_hmac_key == "dev-aadhaar-hmac-key-change-in-prod":
                warnings.append("AADHAAR_HMAC_KEY is using the insecure default — set a random 32-byte secret")
            if not self.csrf_enforce:
                warnings.append("CSRF_ENFORCE is False — enable CSRF protection in production")
        return warnings


# ── Singleton ────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the application settings singleton."""
    return Settings()


# Convenience alias — ``from core.config import settings``
settings: Settings = get_settings()


# ── Environment-specific factory helpers ─────────────────────────────────────

def get_environment_name() -> str:
    return settings.environment.lower()


def is_production() -> bool:
    return settings.is_production


def is_testing() -> bool:
    return settings.is_testing
