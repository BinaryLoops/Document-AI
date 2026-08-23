"""
DocuMind AI — Unified Backend Entry Point
==========================================
Run (development):  uvicorn main:app --reload --port 8000
Run (production):   uvicorn main:app --workers 4 --port 8000

Architecture
------------
  1. core/logging.py    — centralised structured logging (configured first)
  2. core/config.py     — pydantic-settings multi-env config singleton
  3. core/middleware.py — RequestID, Exception, SecurityHeaders, CORS
  4. core/diagnostics.py— startup health checks (non-fatal)
  5. routes/routes.py   — RAGAPIRouter registers all domain endpoints
  6. main.py endpoints  — /, /health, /readiness, /version, /status
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

# ── 1. Logging must be the very first thing configured ───────────────────────
from core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

# ── 2. Load .env before importing anything that reads env vars ───────────────
from dotenv import load_dotenv

_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
    logger.info("✓ Loaded environment variables from %s", _env_path)
else:
    logger.info("No .env file found -- reading from environment only")

# ── 3. Config singleton (reads env vars) ────────────────────────────────────
from core.config import settings, APP_NAME, APP_VERSION, BUILD_DATE

# Warn about production config issues early
for warning in settings.validate_required():
    logger.warning("Config warning: %s", warning)

# ── 4. FastAPI + middleware ──────────────────────────────────────────────────
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.middleware import add_middleware
from core.diagnostics import run_diagnostics, DiagnosticReport
from security.middleware import add_security_middleware

# ── Global state ─────────────────────────────────────────────────────────────
rag_engine    = None
_startup_time = time.time()
_diagnostic_report: Optional[DiagnosticReport] = None
_shutdown_event     = asyncio.Event()


# ── Lifespan (replaces @app.on_event) ───────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown lifecycle manager.

    Startup
    -------
      1. Run diagnostics (non-fatal — server starts regardless)
      2. Initialise embedding model
      3. Initialise FAISS vector database
      4. Initialise LLM (Ollama → HuggingFace → LocalLLM)
      5. Initialise RAG engine
      6. Register all domain routes

    Shutdown
    --------
      - Signal the shutdown event
      - Persist knowledge graph to disk
      - Flush log buffers
    """
    global rag_engine, _diagnostic_report

    logger.info("=" * 60)
    logger.info("  %s v%s — starting up", APP_NAME, APP_VERSION)
    logger.info("  Environment : %s", settings.environment)
    logger.info("  Host:Port   : %s:%d", settings.api_host, settings.effective_port)
    logger.info("=" * 60)

    # ── Load auth store ───────────────────────────────────────────────────
    try:
        from auth.database import load as auth_load
        auth_load()
        logger.info("✓ Auth store loaded")
    except Exception as e:
        logger.error("Auth store load failed: %s", e, exc_info=True)

    # ── Register auth routes (always — independent of RAG engine) ─────────
    try:
        from auth.routes import router as auth_router
        app.include_router(auth_router)
        logger.info("✓ Auth routes registered (/auth/*)")
    except Exception as e:
        logger.error("✗ Auth route registration failed: %s", e, exc_info=True)

    # ── Digital Locker initialisation ─────────────────────────────────────
    try:
        from digilocker.database import DocumentDatabase
        from digilocker.encryption import AES256Encryptor
        from digilocker.vault import FileVault
        from digilocker.pipeline import DocumentPipeline
        from digilocker.routes import create_digilocker_router

        digilocker_db = DocumentDatabase()
        await digilocker_db.initialise()
        app.state.digilocker_db = digilocker_db

        vault = FileVault()
        encryptor = AES256Encryptor()
        dl_pipeline = DocumentPipeline(db=digilocker_db, vault=vault, encryptor=encryptor)

        dl_router = create_digilocker_router(pipeline=dl_pipeline, db=digilocker_db)
        app.include_router(dl_router)
        logger.info("✓ Digital Locker ready (/documents/*)")
    except Exception as e:
        logger.error("✗ Digital Locker init failed: %s", e, exc_info=True)

    # ── Verification Engine initialisation ────────────────────────────────
    try:
        from verification_engine.database import VerificationDatabase
        from verification_engine.pipeline import VerificationPipeline
        from verification_engine.routes import create_verification_router

        verify_db = VerificationDatabase()
        await verify_db.initialise()
        app.state.verify_db = verify_db

        verify_pipeline = VerificationPipeline(db=verify_db)

        verify_router = create_verification_router(pipeline=verify_pipeline, db=verify_db)
        app.include_router(verify_router)
        logger.info("✓ Verification Engine ready (/verify/*)")
    except Exception as e:
        logger.error("✗ Verification Engine init failed: %s", e, exc_info=True)

    # ── AI Intelligence Engine initialisation ────────────────────────────
    try:
        from ai_engine.routes import create_ai_router

        ai_router, assistant_router = create_ai_router()
        app.include_router(ai_router)
        app.include_router(assistant_router)
        logger.info("✓ AI Intelligence Engine ready (/ai/*, /assistant/*)")
    except Exception as e:
        logger.error("✗ AI Intelligence Engine init failed: %s", e, exc_info=True)

    # ── Document Generation Engine ────────────────────────────────────────
    try:
        from generation.database import load as gen_load
        gen_load()
        from generation.routes import router as gen_router, download_router as gen_dl_router
        app.include_router(gen_router)
        app.include_router(gen_dl_router)
        logger.info("✓ Document Generation Engine ready (/generate/*, /generated/*)")
    except Exception as e:
        logger.error("✗ Document Generation Engine init failed: %s", e, exc_info=True)

    # ── Government Knowledge Graph ────────────────────────────────────────
    try:
        from knowledge_graph.gov_graph import GovernmentKnowledgeGraph
        from knowledge_graph.gov_routes import create_graph_router

        gov_kg = GovernmentKnowledgeGraph()
        app.state.gov_kg = gov_kg

        graph_router = create_graph_router(gov_kg)
        app.include_router(graph_router)
        logger.info("✓ Government Knowledge Graph ready (/graph/*)")
    except Exception as e:
        logger.error("✗ Government Knowledge Graph init failed: %s", e, exc_info=True)

    # ── Tracking & Notification System ────────────────────────────────
    try:
        from tracking.database import init_db as tracking_init_db
        from tracking.routes import create_tracking_router

        tracking_db = await tracking_init_db(os.getenv("TRACKING_DB", "tracking.db"))
        app.state.tracking_db = tracking_db

        tracking_router, notif_router = create_tracking_router()
        app.include_router(tracking_router)
        app.include_router(notif_router)
        logger.info("✓ Tracking & Notifications ready (/tracking/*, /notifications/*)")
    except Exception as e:
        logger.error("✗ Tracking & Notifications init failed: %s", e, exc_info=True)

    # ── Enterprise Security (audit log, incident detection, consent) ─────
    try:
        from security.audit import init_audit_db
        from security.incidents import IncidentDetector
        from security.routes import create_security_router

        audit_db_path = os.getenv("AUDIT_DB_PATH", "audit.db")
        app.state.audit_db = await init_audit_db(audit_db_path)

        incident_detector = IncidentDetector()
        app.state.incident_detector = incident_detector

        security_router = create_security_router(incident_detector)
        app.include_router(security_router)
        logger.info("✓ Enterprise Security ready (/security/*)")
    except Exception as e:
        logger.error("✗ Enterprise Security init failed: %s", e, exc_info=True)

    # ── Diagnostics ──────────────────────────────────────────────────────
    logger.info("Running startup diagnostics …")
    _diagnostic_report = await run_diagnostics()
    if _diagnostic_report.has_critical_failures:
        logger.error(
            "Startup diagnostics found critical failures: %s",
            _diagnostic_report.summary,
        )
    else:
        logger.info("Diagnostics complete: %s", _diagnostic_report.summary)

    # ── Component initialisation ─────────────────────────────────────────
    _init_components(app)

    logger.info("✓ %s is ready (startup took %.1fs)", APP_NAME,
                time.time() - _startup_time)
    logger.info("  API docs: http://%s:%d/docs",
                settings.api_host, settings.effective_port)

    yield  # ── application runs here ─────────────────────────────────────

    # ── Graceful shutdown ────────────────────────────────────────────────
    logger.info("Shutting down %s …", APP_NAME)
    _shutdown_event.set()

    # Persist auth store
    try:
        from auth.database import flush as auth_flush
        auth_flush()
        logger.info("✓ Auth store persisted")
    except Exception as e:
        logger.warning("Could not persist auth store: %s", e)

    # Persist knowledge graph if available
    try:
        from knowledge_graph.kg_manager import kg_manager
        kg_manager.save()
        logger.info("✓ Knowledge graph persisted to disk")
    except Exception as e:
        logger.warning("Could not persist knowledge graph: %s", e)

    # Close Digital Locker database
    try:
        if hasattr(app.state, "digilocker_db") and app.state.digilocker_db:
            await app.state.digilocker_db.close()
            logger.info("✓ Digital Locker database closed")
    except Exception as e:
        logger.warning("Could not close DigiLocker DB: %s", e)

    # Persist generation store
    try:
        from generation.database import flush as gen_flush
        gen_flush()
        logger.info("✓ Generation store persisted")
    except Exception as e:
        logger.warning("Could not persist generation store: %s", e)

    # Close Verification Engine database
    try:
        if hasattr(app.state, "verify_db") and app.state.verify_db:
            await app.state.verify_db.close()
            logger.info("✓ Verification Engine database closed")
    except Exception as e:
        logger.warning("Could not close Verification DB: %s", e)

    # Close Tracking database
    try:
        if hasattr(app.state, "tracking_db") and app.state.tracking_db:
            from tracking.database import close_db as tracking_close_db
            await tracking_close_db()
            logger.info("✓ Tracking database closed")
    except Exception as e:
        logger.warning("Could not close Tracking DB: %s", e)

    # Close Security audit database
    try:
        if hasattr(app.state, "audit_db") and app.state.audit_db:
            await app.state.audit_db.close()
            logger.info("✓ Security audit database closed")
    except Exception as e:
        logger.warning("Could not close audit DB: %s", e)

    logger.info("✓ Shutdown complete")


# ── OpenAPI tag metadata (controls ordering/grouping in Swagger UI) ──────────
OPENAPI_TAGS = [
    {"name": "system", "description": "Health, readiness, version, and diagnostics endpoints."},
    {"name": "authentication", "description": "Login, MFA, sessions, tokens, and device management."},
    {"name": "Digital Locker", "description": "Encrypted document upload, storage, and retrieval."},
    {"name": "Verification Engine", "description": "12-step document authenticity verification pipeline."},
    {"name": "AI Intelligence", "description": "Summarization, entity/timeline extraction, case analysis."},
    {"name": "AI Assistant", "description": "Conversational assistant over ingested documents."},
    {"name": "document-generation", "description": "Government document generation, signing, and download."},
    {"name": "document-verification", "description": "Public QR-code based document verification."},
    {"name": "Knowledge Graph", "description": "Entity/relationship graph for government schemes and documents."},
    {"name": "Tracking", "description": "Application/case status tracking."},
    {"name": "Notifications", "description": "User notification delivery and history."},
    {"name": "Security", "description": "Audit log, incident detection, consent management."},
    {"name": "RAG", "description": "Document upload, semantic search, and question answering."},
    {"name": "RAG Intelligence", "description": "Provenance, cross-document, contradiction, and comparison engines."},
]


# ── Application factory ──────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title=APP_NAME,
        description=(
            "Unified document intelligence API — OCR, RAG, Knowledge Graph, "
            "field extraction, classification, and 8 intelligence engines."
        ),
        version=APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=OPENAPI_TAGS,
        contact={"name": "DocuMind AI Team", "url": "https://github.com/"},
        license_info={"name": "Proprietary"},
        lifespan=lifespan,
    )

    # ── Middleware (must be added before routes) ─────────────────────
    add_middleware(app, cors_origins=settings.cors_origin_list)

    # ── Enterprise security middleware (rate limiting, CSRF, input sanitation) ──
    add_security_middleware(
        app,
        rate_limit_rpm=settings.rate_limit_rpm,
        rate_limit_burst=settings.rate_limit_burst,
        csrf_enforce=settings.csrf_enforce,
        session_timeout_minutes=settings.session_timeout_minutes,
    )

    # ── Prometheus metrics (/metrics) ──────────────────────────────
    if settings.enable_metrics:
        try:
            from prometheus_fastapi_instrumentator import Instrumentator

            Instrumentator(
                should_group_status_codes=True,
                should_ignore_untemplated=True,
                excluded_handlers=["/health", "/metrics"],
            ).instrument(app).expose(
                app, endpoint=settings.metrics_path, include_in_schema=False
            )
            logger.info("✓ Prometheus metrics exposed at %s", settings.metrics_path)
        except Exception as e:
            logger.warning("Prometheus instrumentation unavailable: %s", e)

    return app


app = create_app()


# ── Component initialisation (called from lifespan) ──────────────────────────
def _init_components(app: FastAPI) -> None:
    """
    Initialise all heavy components.  Sets the module-level rag_engine.
    Errors are caught and logged — the server always starts.
    """
    global rag_engine

    # ── Step 1: Embedding model ───────────────────────────────────────────
    embedder = None
    try:
        logger.info("Step 1/4 — Creating embedding model (%s) …",
                    settings.embedding_model)
        from embedding.model import create_embedding_model
        embedder = create_embedding_model()
        logger.info("✓ Embedding model ready (dim=%d)", embedder.dimension)
    except Exception as e:
        logger.error("✗ Embedding model failed: %s", e, exc_info=True)
        logger.warning("Starting in degraded mode — no document indexing available")
        return

    # ── Step 2: Vector database ───────────────────────────────────────────
    vector_db = None
    try:
        logger.info("Step 2/4 — Creating FAISS vector database …")
        from storage.vector_db import FaissVectorDatabase
        vector_db = FaissVectorDatabase(dimension=embedder.dimension)
        logger.info("✓ FAISS vector database ready")
    except Exception as e:
        logger.error("✗ Vector database failed: %s", e, exc_info=True)
        return

    # ── Step 3: LLM ───────────────────────────────────────────────────────
    llm = None
    try:
        logger.info("Step 3/4 — Initialising LLM …")
        llm = _init_llm()
    except Exception as e:
        logger.error("✗ LLM initialisation failed: %s", e, exc_info=True)
        # Non-fatal — RAG engine works in retrieve-only mode without LLM

    # ── Step 4: RAG engine ────────────────────────────────────────────────
    try:
        logger.info("Step 4/4 — Creating RAG engine …")
        from rag.engine import RAGEngine
        rag_engine = RAGEngine(
            embedder=embedder,
            vector_db=vector_db,
            llm=llm,
            top_k=settings.top_k,
            search_type=settings.search_type,
        )
        logger.info("✓ RAG engine ready")
    except Exception as e:
        logger.error("✗ RAG engine failed: %s", e, exc_info=True)
        return

    # ── Step 5: Register domain routes ────────────────────────────────────
    try:
        logger.info("Registering API routes …")
        from routes.routes import RAGAPIRouter
        RAGAPIRouter(app, rag_engine)
        logger.info("✓ API routes registered")
    except Exception as e:
        logger.error("✗ Route registration failed: %s", e, exc_info=True)
        logger.warning("Domain endpoints unavailable — only system endpoints active")

def _init_llm():
    """
    LLM selection with automatic fallback chain:
      Ollama (phi) → HuggingFace Inference API → LocalLLM (no internet)
    """
    # Try Ollama first (local, free, no internet)
    try:
        from llm.ollama_model import OllamaLLM
        llm = OllamaLLM(model="phi")
        if llm.available:
            logger.info("✓ LLM: Ollama (model=phi, local, free)")
            return llm
        raise RuntimeError("Ollama not available")
    except Exception as e:
        logger.info("Ollama not available (%s) — trying HuggingFace …", e)

    # Try HuggingFace Inference API
    hf_key = settings.huggingface_api_key or os.getenv("HUGGINGFACE_API_KEY")
    if hf_key:
        try:
            from llm.serverless_model import HuggingFaceInferenceAPI
            llm = HuggingFaceInferenceAPI(
                model_name=settings.huggingface_model,
                api_key=hf_key,
            )
            logger.info("✓ LLM: HuggingFace (%s)", settings.huggingface_model)
            return llm
        except Exception as e:
            logger.warning("HuggingFace LLM failed (%s) — falling back to LocalLLM", e)
    else:
        logger.info(
            "HUGGINGFACE_API_KEY not set — "
            "install Ollama for free local LLM: https://ollama.ai"
        )

    # Final fallback — rule-based LocalLLM (no external dependencies)
    from llm.model import LocalLLM
    logger.warning(
        "✓ LLM: LocalLLM (rule-based fallback — answers may be limited). "
        "Set HUGGINGFACE_API_KEY or install Ollama for better results."
    )
    return LocalLLM()


# ── System endpoints ─────────────────────────────────────────────────────────
# These are always registered regardless of RAG engine state.

@app.get("/", tags=["system"], summary="API root — info and status")
async def root() -> Dict[str, Any]:
    """Return API name, version, status, and links."""
    return {
        "name":        APP_NAME,
        "version":     APP_VERSION,
        "build_date":  BUILD_DATE,
        "environment": settings.environment,
        "status":      "operational" if rag_engine else "degraded",
        "rag_engine":  "ready" if rag_engine else "not initialized",
        "docs":        "/docs",
        "redoc":       "/redoc",
        "health":      "/health",
        "readiness":   "/readiness",
        "version_info":"/version",
    }


@app.get("/version", tags=["system"], summary="Version and build information")
async def version_info() -> Dict[str, Any]:
    """Return detailed version, build, and runtime metadata."""
    import platform
    return {
        "name":        APP_NAME,
        "version":     APP_VERSION,
        "build_date":  BUILD_DATE,
        "environment": settings.environment,
        "python":      platform.python_version(),
        "platform":    platform.system(),
        "uptime_seconds": round(time.time() - _startup_time, 1),
    }


@app.get("/health", tags=["system"], summary="Liveness probe — always returns 200")
async def health() -> Dict[str, Any]:
    """
    Liveness probe.

    Always returns HTTP 200 so load balancers and container orchestrators
    know the process is alive.  Status field reflects RAG availability.
    """
    doc_count = 0
    if rag_engine:
        try:
            doc_count = rag_engine.count_documents()
        except Exception:
            pass

    status = "healthy" if rag_engine else "degraded"
    return {
        "status":         status,
        "version":        APP_VERSION,
        "environment":    settings.environment,
        "rag_engine":     "ready" if rag_engine else "not_initialized",
        "document_count": doc_count,
        "uptime_seconds": round(time.time() - _startup_time, 1),
        "message":        (
            "System is operational"
            if rag_engine
            else "RAG engine not initialized — check startup logs"
        ),
    }


@app.get("/readiness", tags=["system"], summary="Readiness probe — 200 when fully ready")
async def readiness() -> JSONResponse:
    """
    Readiness probe.

    Returns HTTP 200 only when the RAG engine is fully initialised.
    Returns HTTP 503 when the system is still starting up or degraded.

    Use this in Kubernetes readinessProbe / Railway health checks.
    """
    if rag_engine is None:
        return JSONResponse(
            status_code=503,
            content={
                "ready":   False,
                "reason":  "RAG engine not initialized",
                "status":  "starting",
                "version": APP_VERSION,
            },
        )

    # Quick sanity check — embedding model must respond
    try:
        test_embedding = rag_engine.embedder.embed("readiness check")
        if test_embedding is None or len(test_embedding) == 0:
            raise ValueError("Empty embedding returned")
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "ready":  False,
                "reason": f"Embedding model not responding: {e}",
                "status": "degraded",
            },
        )

    doc_count = 0
    try:
        doc_count = rag_engine.count_documents()
    except Exception:
        pass

    return JSONResponse(
        status_code=200,
        content={
            "ready":          True,
            "status":         "ready",
            "version":        APP_VERSION,
            "document_count": doc_count,
            "uptime_seconds": round(time.time() - _startup_time, 1),
        },
    )


@app.get("/status", tags=["system"], summary="Detailed component status")
async def status_detail() -> Dict[str, Any]:
    """
    Return per-component readiness — useful for debugging deployments.
    Preserves the original /status contract while adding new detail.
    """
    components: Dict[str, str] = {
        "rag_engine":  "ready" if rag_engine else "not_initialized",
        "vector_db":   (
            "ready"
            if rag_engine and hasattr(rag_engine, "vector_db")
            else "not_initialized"
        ),
        "llm":         (
            "ready"
            if rag_engine and hasattr(rag_engine, "llm") and rag_engine.llm
            else "not_initialized"
        ),
        "embedder":    (
            "ready"
            if rag_engine and hasattr(rag_engine, "embedder")
            else "not_initialized"
        ),
    }

    # KG availability
    try:
        from knowledge_graph.kg_manager import kg_manager
        kg_stats = kg_manager.get_stats()
        components["knowledge_graph"] = (
            f"ready (entities={kg_stats.get('entity_count', 0)}, "
            f"relations={kg_stats.get('relation_count', 0)})"
        )
    except Exception:
        components["knowledge_graph"] = "unavailable"

    # Firebase availability
    components["firebase"] = "enabled" if settings.firebase_available else "disabled"

    diagnostics_summary = (
        _diagnostic_report.summary if _diagnostic_report else "not run"
    )

    return {
        "api":     "running",
        "version": APP_VERSION,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - _startup_time, 1),
        "components":  components,
        "diagnostics": diagnostics_summary,
        "endpoints": {
            "root":      "/",
            "health":    "/health",
            "readiness": "/readiness",
            "version":   "/version",
            "docs":      "/docs",
            "upload":    "/upload"    if rag_engine else "unavailable",
            "query":     "/query"     if rag_engine else "unavailable",
            "search":    "/search"    if rag_engine else "unavailable",
            "kg_stats":  "/kg/stats"  if rag_engine else "unavailable",
        },
    }


@app.get("/diagnostics", tags=["system"],
         summary="Startup diagnostics report (last run)")
async def diagnostics_report() -> Dict[str, Any]:
    """
    Return the full startup diagnostics report from the last server start.

    Useful for debugging missing dependencies or misconfigured services.
    """
    if _diagnostic_report is None:
        return {"message": "Diagnostics not yet run", "checks": []}
    return _diagnostic_report.to_dict()


# ── SIGTERM / SIGINT graceful shutdown ───────────────────────────────────────
def _handle_signal(sig: int, frame: Any) -> None:  # noqa: ANN001
    logger.info("Received signal %d — initiating graceful shutdown …", sig)
    # asyncio event will be set by the lifespan shutdown block
    # uvicorn handles the actual process exit


for _sig in (signal.SIGTERM, signal.SIGINT):
    try:
        signal.signal(_sig, _handle_signal)
    except (OSError, ValueError):
        pass  # Windows doesn't support all signals in all contexts


# ── Dev entry point ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    logger.info("Starting %s in %s mode …", APP_NAME, settings.environment)
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.effective_port,
        reload=settings.is_development,
        workers=1 if settings.is_development else settings.workers,
        log_level=settings.effective_log_level.lower(),
        access_log=False,  # Our RequestIDMiddleware handles access logging
    )
