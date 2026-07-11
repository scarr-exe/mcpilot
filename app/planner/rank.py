"""
Deterministic composite ranking of MCP candidates within a capability.

This is intentionally NOT an LLM call. The score is a fixed formula over
real GitHub metadata (stars, commit recency, open issue count), so it's
reproducible and defensible — the LLM's job (in explain.py) is only to
narrate the score in plain English, never to invent it.

    score = (stars_score      * RANK_WEIGHT_STARS)
          + (recency_score    * RANK_WEIGHT_RECENCY)
          + (issue_health_score * RANK_WEIGHT_ISSUE_HEALTH)

All three sub-scores are normalized to [0, 1] before weighting.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from app.config import settings

# Stars beyond this are treated as "maxed out" — prevents one mega-popular
# repo (10k+ stars) from completely dominating the score on stars alone.
STARS_SATURATION_POINT = 2000

# A repo with no commits in this many days scores ~0 on recency.
RECENCY_HALF_LIFE_DAYS = 180

# Open issues beyond this are treated as "maximally unhealthy".
ISSUE_SATURATION_POINT = 100


def _stars_score(stars: int) -> float:
    if stars <= 0:
        return 0.0
    # log-scaled so the difference between 10 and 100 stars matters more
    # than the difference between 5000 and 5090
    return min(math.log1p(stars) / math.log1p(STARS_SATURATION_POINT), 1.0)


def _recency_score(last_commit_at: str | None) -> float:
    if not last_commit_at:
        return 0.0
    try:
        commit_time = datetime.fromisoformat(last_commit_at.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    days_since = (datetime.now(timezone.utc) - commit_time).total_seconds() / 86400
    if days_since < 0:
        days_since = 0
    # exponential decay with the configured half-life
    return math.pow(0.5, days_since / RECENCY_HALF_LIFE_DAYS)


def _issue_health_score(open_issues: int) -> float:
    if open_issues <= 0:
        return 1.0
    return max(1.0 - (open_issues / ISSUE_SATURATION_POINT), 0.0)


def score_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """
    Returns the candidate dict augmented with 'score' and 'score_breakdown'
    (the raw sub-scores, kept around so explain.py can cite them directly
    instead of the LLM inventing justifications).
    """
    stars_score = _stars_score(candidate.get("stars", 0))
    recency_score = _recency_score(candidate.get("last_commit_at"))
    issue_health_score = _issue_health_score(candidate.get("open_issues", 0))

    composite = (
        stars_score * settings.RANK_WEIGHT_STARS
        + recency_score * settings.RANK_WEIGHT_RECENCY
        + issue_health_score * settings.RANK_WEIGHT_ISSUE_HEALTH
    )

    return {
        **candidate,
        "score": round(composite, 4),
        "score_breakdown": {
            "stars_score": round(stars_score, 4),
            "recency_score": round(recency_score, 4),
            "issue_health_score": round(issue_health_score, 4),
        },
    }


def rank_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Scores and sorts candidates descending, truncated to
    settings.TOP_N_PER_CAPABILITY.
    """
    scored = [score_candidate(c) for c in candidates]
    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[: settings.TOP_N_PER_CAPABILITY]


def rank_all(matches: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """Applies rank_candidates to every capability's candidate list."""
    return {capability: rank_candidates(candidates) for capability, candidates in matches.items()}


if __name__ == "__main__":
    from app.planner.match import match_capabilities
    import json

    matches = match_capabilities(["web-scraping"])
    ranked = rank_all(matches)
    for capability, candidates in ranked.items():
        print(f"\n{capability}:")
        for c in candidates:
            print(
                f"  {c['repo_full_name']} — score={c['score']} "
                f"(stars={c['score_breakdown']['stars_score']}, "
                f"recency={c['score_breakdown']['recency_score']}, "
                f"issues={c['score_breakdown']['issue_health_score']})"
            )