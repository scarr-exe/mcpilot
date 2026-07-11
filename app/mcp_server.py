"""
Wraps the FastAPI app (app/main.py) as an MCP server using FastMCP's
automatic OpenAPI-based conversion — this is the pattern OKX's own
A2MCP guide recommends (FastAPI -> FastMCP -> deploy with HTTPS).

Transport is environment-driven:
  - Local dev / MCP Inspector testing: stdio (the default — no env vars needed)
  - Production deployment (Railway/Fly.io): HTTP, so OKX.AI and other
    remote agents can reach it over your public HTTPS domain

    Set MCP_TRANSPORT=http in production (Railway sets PORT automatically).
"""
from __future__ import annotations

import os

from fastmcp import FastMCP

from app.main import app as fastapi_app

mcp = FastMCP.from_fastapi(app=fastapi_app, name="mcp-intelligence-platform")

if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "http":
        port = int(os.getenv("PORT", "8000"))
        mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
    else:
        # stdio — used by MCP Inspector and other local clients
        mcp.run()