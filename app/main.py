"""
FastAPI entrypoint. Exposes a single POST /plan endpoint that runs the
full pipeline (see app/planner/pipeline.py). This module is also
imported by app/mcp_server.py, which wraps /plan as an MCP tool.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models import PlanRequest, PlanResponse
from app.planner.pipeline import run_plan

logging.basicConfig(level=settings.LOG_LEVEL.upper())
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MCP Intelligence Platform",
    description="The capability planner for AI agents — decomposes a goal, "
    "discovers and ranks real MCP servers, and assembles an execution workflow.",
    version="0.1.0",
)

# Allows the demo landing page (web/) to call this API directly from the
# browser. Fine for this read-mostly, no-auth endpoint — tighten
# allow_origins to a specific domain if this ever needs to be locked down.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/plan", response_model=PlanResponse)
def plan(request: PlanRequest) -> PlanResponse:
    try:
        result = run_plan(request.goal)
        return PlanResponse(**result)
    except Exception as e:
        logger.exception("Failed to generate plan for goal: %s", request.goal)
        raise HTTPException(status_code=500, detail=f"Planning failed: {e}") from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.APP_ENV == "development")