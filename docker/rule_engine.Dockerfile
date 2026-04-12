FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY rule_engine /app/rule_engine
COPY shared /app/shared

RUN pip install --upgrade pip && pip install ".[rule-engine]"

CMD ["sh", "-c", "uvicorn rule_engine.app:app --host 0.0.0.0 --port ${PORT:-8001}"]
