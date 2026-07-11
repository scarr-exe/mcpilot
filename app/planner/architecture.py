"""
For larger/agentic goals, generates a high-level system architecture
sketch — the reasoning layer, memory strategy, and external tools an
agent builder would need, given the workflow already assembled.

This is intentionally high-level and advisory, not a second workflow —
it answers "what should the surrounding agent look like," not "what
order do the MCP calls happen in" (that's workflow.py's job).
"""
from __future__ import annotations

import json
from typing import Any

from app.config import settings
from app.llm.client import get_groq_client

SYSTEM_PROMPT = """You are an AI agent architecture advisor. Given a \
user's goal and its execution workflow (an ordered sequence of MCP \
calls), output a high-level system architecture sketch for the agent \
that would run this workflow.

Output ONLY a JSON object with this exact shape, no other text:

{
  "reasoning_layer": "1-2 sentences on what kind of reasoning/planning \
this agent needs (e.g. single-shot, ReAct loop, multi-step planner)",
  "memory": "1-2 sentences on what the agent needs to remember across \
steps, if anything, and a suggested approach (e.g. none needed, \
short-term scratch context, persistent vector store)",
  "external_tools": "1-2 sentences on any tools/integrations beyond the \
MCPs already listed in the workflow that this agent would likely need \
(e.g. notification channel, human-in-the-loop approval step)",
  "notes": "1-2 sentences of any other relevant architectural guidance \
or caveats, e.g. error handling, rate limits, or steps where the \
workflow's MCP choice deserves a fallback"
}

Rules:
- Ground every claim in the specific goal and workflow provided — do \
not give generic boilerplate that would apply to any agent
- If a section genuinely doesn't apply (e.g. no memory needed for a \
single-shot task), say so directly rather than padding with vague text
"""


def _build_user_prompt(goal: str, workflow: list[dict[str, Any]]) -> str:
    return f"Goal: {goal}\nWorkflow:\n{json.dumps(workflow, indent=2)}"


def generate_architecture(goal: str, workflow: list[dict[str, Any]]) -> dict[str, str]:
    """
    Returns {reasoning_layer, memory, external_tools, notes}. Falls back
    to a minimal templated response if the LLM call fails after retries.
    """
    if not workflow:
        return {
            "reasoning_layer": "No workflow steps available to base an architecture on.",
            "memory": "N/A",
            "external_tools": "N/A",
            "notes": "Run decomposition and workflow generation first.",
        }

    client = get_groq_client()
    last_error: Exception | None = None
    required_keys = {"reasoning_layer", "memory", "external_tools", "notes"}

    for attempt in range(3):
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(goal, workflow)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        raw = response.choices[0].message.content
        try:
            parsed = json.loads(raw)
            if not required_keys.issubset(parsed.keys()):
                raise ValueError(f"Missing keys: {required_keys - parsed.keys()}")
            return {k: str(parsed[k]).strip() for k in required_keys}
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            continue

    print(f"  [architecture] LLM architecture generation failed after 3 "
          f"attempts ({last_error}), using templated fallback")
    step_count = len(workflow)
    return {
        "reasoning_layer": f"A {step_count}-step sequential pipeline; "
        f"a simple single-shot planner should suffice unless steps need conditional branching.",
        "memory": "Short-term context passed between steps is likely sufficient; "
        "no persistent memory store indicated by this workflow alone.",
        "external_tools": "None beyond the MCPs already listed in the workflow.",
        "notes": "Architecture generation fell back to a template — "
        "review manually for goal-specific nuance.",
    }


if __name__ == "__main__":
    from app.planner.match import match_capabilities
    from app.planner.rank import rank_all
    from app.planner.workflow import build_workflow

    goal = "Build an AI accountant that reads invoices and files taxes"
    capabilities = ["ocr", "invoice-parsing", "spreadsheet-integration"]
    matches = match_capabilities(capabilities)
    ranked = rank_all(matches)
    workflow = build_workflow(goal, ranked)
    architecture = generate_architecture(goal, workflow)
    print(json.dumps(architecture, indent=2))