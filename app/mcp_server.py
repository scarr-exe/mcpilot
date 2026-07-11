"""
Wraps the FastAPI app (app/main.py) as an MCP server using FastMCP's
automatic OpenAPI-based conversion — this is the pattern OKX's own
A2MCP guide recommends (FastAPI -> FastMCP -> deploy with HTTPS).

Run standalone for local testing with MCP Inspector:
    python -m app.mcp_server

In production, this is what gets deployed behind your public domain.
"""
from __future__ import annotations

from fastmcp import FastMCP

from app.main import app as fastapi_app

mcp = FastMCP.from_fastapi(app=fastapi_app, name="mcp-intelligence-platform")

if __name__ == "__main__":
    # Default FastMCP dev transport (stdio) — for HTTP/SSE transport in
    # production, see FastMCP's deployment docs for the run() args that
    # match your hosting choice (Railway/Fly.io).
    mcp.run()