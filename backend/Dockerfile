# ClauseGuard API.
#
#   docker build -t clauseguard-api ./backend
#   docker build -t clauseguard-api --build-arg INSTALL_ML=false ./backend      # slim, keyword classifier only
#   docker build -t clauseguard-api --build-arg SPACY_MODEL=en_core_web_sm ./backend
#
# INSTALL_ML=true (default) installs the spaCy pipeline named by SPACY_MODEL
# so the trained Layer 1 classifier runs; with false, classifier.py falls back
# to keyword rules and the image stays small.
#
# Runtime contract (Railway, compose, plain docker):
#   PORT            port to listen on (default 8000)
#   DATABASE_URL    postgres://, postgresql:// or postgresql+asyncpg:// (normalised by config.py)
#   serve.py listens on IPv4 and IPv6: Railway's private network is IPv6
#   (api.railway.internal) while compose, Docker's port proxy and the
#   HEALTHCHECK below connect over IPv4.

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Tesseract reads scanned contracts. PyMuPDF shells out to it, so this is a
# system package rather than a Python one; its own layer because it changes
# far less often than the code. ~60MB with the English data.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Exact, reproducible dependency set. The spaCy model is deliberately not in
# the lockfile — it is its own cached layer below, selectable by build arg.
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt

# Layer 1 language model. Installed from the pinned release wheel rather than
# `spacy download` (which resolves "latest compatible" at build time), so two
# builds of the same commit produce the same image.
ARG INSTALL_ML=true
ARG SPACY_MODEL=en_core_web_sm
ARG SPACY_MODEL_VERSION=3.8.0
ENV SPACY_MODEL=$SPACY_MODEL
RUN if [ "$INSTALL_ML" = "true" ]; then \
      pip install --no-cache-dir \
        "https://github.com/explosion/spacy-models/releases/download/${SPACY_MODEL}-${SPACY_MODEL_VERSION}/${SPACY_MODEL}-${SPACY_MODEL_VERSION}-py3-none-any.whl"; \
    fi

# Application code last, so code changes never invalidate the layers above.
# .dockerignore keeps tests, the training sandbox, the venv and .env out.
COPY . .

# Run as an unprivileged user. DSPy/LiteLLM keep an on-disk cache; point it
# at a writable location instead of the read-only application directory.
RUN useradd --system --uid 10001 --create-home --home-dir /home/app app \
    && chown -R app:app /app
USER app
ENV HOME=/home/app \
    DSPY_CACHEDIR=/tmp/dspy_cache

EXPOSE 8000

# Honoured by docker/compose (Railway runs its own deploy-time check against
# /api/health). Any non-2xx — e.g. the 503 the API returns while the
# database is unavailable — fails the check.
HEALTHCHECK --start-period=90s --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/api/health', timeout=4)"

# Migrations run inside the app's startup (database.init_db -> alembic
# upgrade head), so a plain container start brings the schema to head.
# serve.py reads $PORT and binds both address families (see its docstring).
CMD ["python", "serve.py"]
