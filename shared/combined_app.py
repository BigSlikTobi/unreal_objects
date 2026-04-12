"""Combined FastAPI application that runs Rule Engine + Decision Center
in a single process.  Eliminates one container and replaces internal HTTP
calls with direct function calls.

Usage:
    uvicorn shared.combined_app:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

from fastapi import FastAPI

from rule_engine.app import app as rule_engine_app, store as rule_store
from decision_center.app import app as decision_center_app
from decision_center.evaluator import use_local_rule_store


app = FastAPI(title="Unreal Objects Backend (combined)")

# Wire the evaluator to read from the Rule Engine store directly.
use_local_rule_store(rule_store)

# Mount both services.  Each keeps its own /v1/... prefix, so all existing
# URLs work unchanged when callers hit:
#   GET /rule-engine/v1/groups/...
#   POST /decision-center/v1/decide
app.mount("/rule-engine", rule_engine_app)
app.mount("/decision-center", decision_center_app)


# Top-level health check that covers both services.
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "combined_backend",
        "services": ["rule_engine", "decision_center"],
    }
