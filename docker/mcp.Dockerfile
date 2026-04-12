FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY mcp_server /app/mcp_server
COPY shared /app/shared

RUN pip install --upgrade pip && pip install ".[mcp-server]"

CMD ["sh", "-c", "python mcp_server/server.py --transport streamable-http --host 0.0.0.0 --port ${PORT:-8000} --auth-enabled --admin-api-key ${MCP_ADMIN_API_KEY:?missing MCP_ADMIN_API_KEY}"]
