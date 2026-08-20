# ClauseGuard API.
#
#   docker build -t clauseguard-api ./backend
#   docker build -t clauseguard-api --build-arg INSTALL_ML=false ./backend   # slim, keyword classifier only
#
# INSTALL_ML=true (default) downloads the spaCy language model (~600MB layer)
# so the trained Layer 1 classifier runs; with false, classifier.py falls
# back to keyword rules and the image stays small.

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ARG INSTALL_ML=true
RUN if [ "$INSTALL_ML" = "true" ]; then \
      python -m spacy download en_core_web_lg; \
    fi

COPY . .

EXPOSE 8000

# Migrations run inside the app's startup (database.init_db → alembic
# upgrade head), so a plain container start brings the schema to head.
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
