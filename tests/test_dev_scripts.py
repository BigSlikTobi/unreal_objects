from pathlib import Path


def test_backend_stack_script_exists_and_restarts_expected_services():
    script_path = Path("scripts/start_backend_stack.sh")

    assert script_path.exists()

    script = script_path.read_text()

    assert "pkill -f" in script
    assert "uvicorn rule_engine.app:app --port 8001 --host 0.0.0.0" in script
    assert "uvicorn decision_center.app:app --port 8002 --host 0.0.0.0" in script
    assert "python mcp_server/server.py \\" in script
    assert "--transport streamable-http" in script
    assert "--host 0.0.0.0" in script
    assert "--port 8000" in script
    assert "--auth-enabled" in script
    assert "--admin-api-key admin-secret" in script
