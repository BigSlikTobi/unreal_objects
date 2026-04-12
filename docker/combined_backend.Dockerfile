FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY rule_engine /app/rule_engine
COPY decision_center /app/decision_center
COPY shared /app/shared
COPY schemas /app/schemas

RUN pip install --upgrade pip && pip install ".[decision-center]"

CMD ["sh", "-c", "uvicorn shared.combined_app:app --host 0.0.0.0 --port ${PORT:-8001}"]
