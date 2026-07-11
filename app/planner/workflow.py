"""
Takes the original goal, the decomposed capabilities, and their ranked+
explained MCP matches, and assembles an ordered execution pipeline.

This is where "here are 5 separate capability matches" becomes "here is
the sequence you'd actually wire together to accomplish the goal."
"""
from __future__ import annotations

import json
from typing import Any

from app.config import settings
from app.llm.client import get_groq_client

SYSTEM_PROMPT = """You are a workflow planning engine. Given a user's \
goal, its decomposed capabilities, and the top-ranked MCP for each \
capability, output an ordered execution pipeline.

Output ONLY a JSON object with this exact shape, no other text:

{
  "workflow": [
    {
      "step": 1,
      "capability": "...",
      "mcp": "owner/repo",
      "reason": "1 sentence on why this step happens at this point in the sequence"
    },
    ...
  ]
}

Rules:
- Use ONLY the mcp values provided to you (the top-ranked repo_full_name \
for each capability) — do not invent or substitute a different MCP
- Order steps by actual data/control flow dependency (e.g. OCR before \
data extraction, extraction before spreadsheet write), not by the order \
capabilities happened to be listed
- If two steps could reasonably run in parallel, still give them \
sequential step numbers but note the parallelism in the reason
- Include every capability provided exactly once
"""


def _build_user_prompt(goal: str, top_matches: dict[str, str]) -> str:
    lines = [f"Goal: {goal}", "Capabilities and their top-ranked MCP:"]
    for capability, mcp in top_matches.items():
        lines.append(f"  - {capability}: {mcp}")
    return "\n".join(lines)


def _extract_top_matches(ranked: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    """Reduces each capability's ranked candidate list to just its #1 pick."""
    top: dict[str, str] = {}
    for capability, candidates in ranked.items():
        if candidates:
            top[capability] = candidates[0]["repo_full_name"]
    return top


def build_workflow(goal: str, ranked: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """
    Returns an ordered list of workflow steps. Falls back to a naive
    sequential ordering (input order, no reasoning) if the LLM call fails
    after retries — so a Groq hiccup never breaks the whole /plan response.
    """
    top_matches = _extract_top_matches(ranked)
    if not top_matches:
        return []

    client = get_groq_client()
    last_error: Exception | None = None

    for attempt in range(3):
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(goal, top_matches)},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw = response.choices[0].message.content
        try:
            parsed = json.loads(raw)
            workflow = parsed.get("workflow")
            if not isinstance(workflow, list) or not workflow:
                raise ValueError(f"Malformed shape: {parsed}")
            # Sanity check every step references a real, provided MCP —
            # guards against the LLM inventing a repo that isn't in
            # top_matches
            valid_mcps = set(top_matches.values())
            for step in workflow:
                if step.get("mcp") not in valid_mcps:
                    raise ValueError(f"Step references unknown MCP: {step}")
            return sorted(workflow, key=lambda s: s.get("step", 0))
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            continue

    print(f"  [workflow] LLM workflow generation failed after 3 attempts "
          f"({last_error}), using naive sequential fallback")
    return [
        {
            "step": i + 1,
            "capability": capability,
            "mcp": mcp,
            "reason": "Sequential fallback ordering (LLM workflow generation unavailable).",
        }
        for i, (capability, mcp) in enumerate(top_matches.items())
    ]


if __name__ == "__main__":
    from app.planner.match import match_capabilities
    from app.planner.rank import rank_all

    goal = "Build an AI accountant that reads invoices and files taxes"
    capabilities = ["ocr", "invoice-parsing", "spreadsheet-integration"]
    matches = match_capabilities(capabilities)
    ranked = rank_all(matches)
    workflow = build_workflow(goal, ranked)
    print(json.dumps(workflow, indent=2))