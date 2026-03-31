FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY rule_engine /app/rule_engine
COPY decision_center /app/decision_center
COPY mcp_server /app/mcp_server
COPY company_server /app/company_server
COPY shared /app/shared
COPY evals /app/evals
COPY support_company /app/support_company
COPY schemas /app/schemas

RUN pip install --upgrade pip && pip install .

CMD ["sh", "-c", "uvicorn mcp_server.tool_agent:app --host 0.0.0.0 --port ${PORT:-8003}"]

