"""
Generates human-readable explanations for why each ranked MCP was
recommended. Critically: the LLM is only allowed to narrate numbers it's
given (stars, days-since-commit-derived recency, open issues, the score
breakdown from rank.py) — it never invents metrics like "community
rating" or "reliability" that aren't backed by real data.
"""
from __future__ import annotations

import json
from typing import Any

from app.config import settings
from app.llm.client import get_groq_client

SYSTEM_PROMPT = """You explain why specific MCP servers were recommended \
for a given capability, using ONLY the data provided to you (stars, \
last_commit_at, open_issues, and the precomputed score_breakdown). Do \
NOT invent metrics, ratings, or claims not present in the data. If the \
data is sparse for a candidate, say so plainly rather than filling in \
confident-sounding language.

Output ONLY a JSON object with this exact shape, no other text:

{
  "explanations": [
    {"repo_full_name": "...", "explanation": "2-3 sentence explanation"},
    ...
  ]
}
"""


def _build_user_prompt(capability: str, ranked_candidates: list[dict[str, Any]]) -> str:
    trimmed = [
        {
            "repo_full_name": c["repo_full_name"],
            "summary": c.get("summary", ""),
            "stars": c.get("stars", 0),
            "open_issues": c.get("open_issues", 0),
            "last_commit_at": c.get("last_commit_at"),
            "score": c.get("score"),
            "score_breakdown": c.get("score_breakdown"),
        }
        for c in ranked_candidates
    ]
    return f"Capability: {capability}\nRanked candidates:\n{json.dumps(trimmed, indent=2)}"


def explain_ranking(capability: str, ranked_candidates: list[dict[str, Any]]) -> dict[str, str]:
    """
    Returns {repo_full_name: explanation_text} for the given ranked
    candidates. Falls back to a templated explanation (still built from
    real data, just not LLM-phrased) if the LLM call fails after retries.
    """
    if not ranked_candidates:
        return {}

    client = get_groq_client()
    last_error: Exception | None = None

    for attempt in range(3):
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(capability, ranked_candidates)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        raw = response.choices[0].message.content
        try:
            parsed = json.loads(raw)
            explanations = parsed.get("explanations")
            if not isinstance(explanations, list):
                raise ValueError(f"Malformed shape: {parsed}")
            result = {}
            for item in explanations:
                repo = item.get("repo_full_name")
                text = item.get("explanation")
                if repo and text:
                    result[repo] = text.strip()
            if not result:
                raise ValueError("No valid explanations parsed")
            return result
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            continue

    # Fallback: templated explanation built directly from real numbers,
    # so a Groq hiccup never breaks the whole /plan response.
    print(f"  [explain] LLM explanation failed for '{capability}' after 3 attempts "
          f"({last_error}), using templated fallback")
    return {
        c["repo_full_name"]: (
            f"{c['repo_full_name']} has {c.get('stars', 0)} stars and "
            f"{c.get('open_issues', 0)} open issues, with a composite "
            f"score of {c.get('score')} based on popularity, commit "
            f"recency, and issue health."
        )
        for c in ranked_candidates
    }


def explain_all(ranked: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, str]]:
    """Applies explain_ranking to every capability's ranked candidate list."""
    return {
        capability: explain_ranking(capability, candidates)
        for capability, candidates in ranked.items()
    }


if __name__ == "__main__":
    from app.planner.match import match_capabilities
    from app.planner.rank import rank_all

    matches = match_capabilities(["web-scraping"])
    ranked = rank_all(matches)
    explanations = explain_all(ranked)
    print(json.dumps(explanations, indent=2))