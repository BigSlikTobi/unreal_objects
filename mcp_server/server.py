import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Unreal Objects", host="0.0.0.0")

RULE_ENGINE_URL = "http://127.0.0.1:8001"
DECISION_CENTER_URL = "http://127.0.0.1:8002"

@mcp.tool()
async def list_rule_groups():
    """Lists all business rule groups from the Rule Engine."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{RULE_ENGINE_URL}/v1/groups")
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def get_rule_group(group_id: str):
    """Gets a specific rule group with its rules."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{RULE_ENGINE_URL}/v1/groups/{group_id}")
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def evaluate_action(request_description: str, context_json: str, group_id: str = None):
    """Evaluates an action against a group's rules via Decision Center."""
    async with httpx.AsyncClient() as client:
        params = {
            "request_description": request_description,
            "context": context_json
        }
        if group_id:
            params["group_id"] = group_id
        resp = await client.get(f"{DECISION_CENTER_URL}/v1/decide", params=params)
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def submit_approval(request_id: str, approved: bool, approver: str):
    """Submits user approval for a pending decision."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DECISION_CENTER_URL}/v1/decide/{request_id}/approve",
            json={"approved": approved, "approver": approver}
        )
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def get_decision_log(log_type: str, request_id: str = None):
    """Retrieves decision logs. log_type can be 'atomic', 'chains', or 'chain' (requires request_id)."""
    async with httpx.AsyncClient() as client:
        if log_type == "atomic":
            url = f"{DECISION_CENTER_URL}/v1/logs/atomic"
        elif log_type == "chains":
            url = f"{DECISION_CENTER_URL}/v1/logs/chains"
        elif log_type == "chain":
            if not request_id:
                raise ValueError("request_id is required for log_type 'chain'")
            url = f"{DECISION_CENTER_URL}/v1/logs/chains/{request_id}"
        else:
            raise ValueError(f"Invalid log_type: {log_type}")
            
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def get_pending():
    """Lists pending approval requests."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{DECISION_CENTER_URL}/v1/pending")
        resp.raise_for_status()
        return resp.json()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Unreal Objects MCP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to for SSE transport")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to for SSE transport")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="Transport mode")
    
    args = parser.parse_args()
    
    if args.transport == "sse":
        print(f"Starting Unreal Objects MCP Server (SSE) on http://{args.host}:{args.port}")
        # Run FastMCP using an ASGI server
        import uvicorn
        from starlette.middleware.cors import CORSMiddleware
        
        # We must add CORS middleware specifically for the /messages POST endpoint
        # so external clients (like browser-based Agents) can make cross-origin requests
        app = CORSMiddleware(
            mcp.sse_app(),
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        # Default STDIO transport for local clients
        mcp.run()

if __name__ == "__main__":
    main()

