# syntax=docker/dockerfile:1
# =============================================================================
# DocuMind AI Backend — Production Dockerfile
# =============================================================================
# Multi-stage build:
#   1. "builder" — installs Python dependencies into an isolated venv
#   2. "runtime" — copies the venv + app code onto a slim base with only the
#      system libraries needed to run (tesseract, fonts, curl for healthcheck)
#
# Build:
#   docker build -t documind-backend:latest .
#
# Run:
#   docker run -p 8000:8000 --env-file .env documind-backend:latest
# =============================================================================

ARG PYTHON_VERSION=3.11-slim-bookworm

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION} AS builder

# Build-time system dependencies (compilers for packages without wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Create an isolated virtual environment so the runtime stage can copy it
# wholesale without needing build tools.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Pre-download the spaCy English model used by the Knowledge Graph NER
RUN python -m spacy download en_core_web_sm || true

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION} AS runtime

LABEL org.opencontainers.image.title="DocuMind AI Backend" \
      org.opencontainers.image.description="Unified document intelligence API — OCR, RAG, Knowledge Graph, verification, generation" \
      org.opencontainers.image.licenses="Proprietary"

# Runtime-only system dependencies:
#   tesseract-ocr        — OCR engine used by document/ocr_processor.py
#   libgl1 / libglib2.0-0 — required by opencv-python at import time
#   curl                  — used by the container HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-built virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    API_HOST=0.0.0.0 \
    API_PORT=8000

# Non-root user for defense-in-depth
RUN groupadd --gid 1000 documind && \
    useradd --uid 1000 --gid documind --shell /bin/bash --create-home documind

WORKDIR /app

# Copy application code (see .dockerignore for exclusions)
COPY --chown=documind:documind . .

# Directories the app writes to at runtime (databases, vault, generated PDFs)
RUN mkdir -p /app/vault /app/gen_keys /app/generated_pdfs /app/logs /app/data && \
    chown -R documind:documind /app

USER documind

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# workers is read from the WORKERS env var by main.py in production mode.
# Use a shell entrypoint so $PORT (Railway/Cloud Run style) is respected too.
CMD ["sh", "-c", "uvicorn main:app --host ${API_HOST:-0.0.0.0} --port ${PORT:-${API_PORT:-8000}} --workers ${WORKERS:-2}"]
