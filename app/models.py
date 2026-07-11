"""
Request/response schemas for the /plan endpoint. Kept separate from
main.py so the MCP wrapper (mcp_server.py) can import the same shapes
without pulling in FastAPI-specific code.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class PlanRequest(BaseModel):
    goal: str = Field(..., min_length=1, description="The user's natural-language goal")


class ScoreBreakdown(BaseModel):
    stars_score: float
    recency_score: float
    issue_health_score: float


class RankedCandidate(BaseModel):
    repo_full_name: str
    name: str
    summary: str | None = None
    stars: int
    open_issues: int
    last_commit_at: str | None = None
    capability_tags: list[str] = []
    score: float
    score_breakdown: ScoreBreakdown
    explanation: str | None = None


class WorkflowStep(BaseModel):
    step: int
    capability: str
    mcp: str
    reason: str


class Architecture(BaseModel):
    reasoning_layer: str
    memory: str
    external_tools: str
    notes: str


class PlanResponse(BaseModel):
    goal: str
    capabilities: list[str]
    unmatched_capabilities: list[str] = Field(
        default_factory=list,
        description="Capabilities with no registry matches — surfaced explicitly rather than silently dropped",
    )
    recommendations: dict[str, list[RankedCandidate]]
    workflow: list[WorkflowStep]
    architecture: Architecture