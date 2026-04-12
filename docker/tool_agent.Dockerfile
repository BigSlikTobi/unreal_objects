FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY mcp_server /app/mcp_server
COPY shared /app/shared

RUN pip install --upgrade pip && pip install ".[tool-agent]"

CMD ["sh", "-c", "uvicorn mcp_server.tool_agent:app --host 0.0.0.0 --port ${PORT:-8003}"]
