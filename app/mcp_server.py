"""
Wraps the FastAPI app (app/main.py) as an MCP server using FastMCP's
automatic OpenAPI-based conversion — this is the pattern OKX's own
A2MCP guide recommends (FastAPI -> FastMCP -> deploy with HTTPS).

Transport is environment-driven:
  - Local dev / MCP Inspector testing: stdio (the default — no env vars needed)
  - Production (Railway): SSE transport, served at /sse.
    OKX.AI's evaluator expects the older SSE transport (2024-11-05 spec),
    not streamable-http (2025-03-26 spec) — the latter returns HTTP 406
    without the correct Accept headers that most MCP clients don't send.

    Set MCP_TRANSPORT=sse in production (Railway sets PORT automatically).
    Register the endpoint as: https://<your-domain>/sse on OKX.AI.
"""
from __future__ import annotations

import os

from fastmcp import FastMCP

from app.main import app as fastapi_app

mcp = FastMCP.from_fastapi(app=fastapi_app, name="mcp-intelligence-platform")

if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "sse":
        port = int(os.getenv("PORT", "8000"))
        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        # stdio — used by MCP Inspector and other local clients
        mcp.run()