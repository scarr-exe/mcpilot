"""
Turns a user's natural-language goal into a list of atomic technical
capabilities. This is the first step of the planning pipeline — everything
downstream (matching, ranking, workflow, architecture) operates on this
capability list rather than the raw goal string.
"""
from __future__ import annotations

import json

from app.config import settings
from app.llm.client import get_groq_client

SYSTEM_PROMPT = """You are a capability decomposition engine. Given a \
user's goal, break it down into the atomic technical capabilities \
required to achieve it.

Output ONLY a JSON object with this exact shape, no other text:

{
  "capabilities": ["capability1", "capability2", ...]
}

Rules:
- 2 to 8 capabilities
- lowercase, short phrases (e.g. "ocr", "web-search", "database", \
"spreadsheet-integration", "translation", "report-generation")
- name CAPABILITIES, not products or company names
- order them roughly in the sequence they'd be needed, if there's a \
natural pipeline order
- be specific enough to be useful for matching against a tool registry, \
but don't over-fragment trivial sub-steps
"""


def decompose_goal(goal: str) -> list[str]:
    """
    Returns a list of capability strings. Raises RuntimeError if the LLM
    repeatedly fails to produce valid, non-empty output.
    """
    client = get_groq_client()
    last_error: Exception | None = None

    for attempt in range(3):
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Goal: {goal}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw = response.choices[0].message.content
        try:
            parsed = json.loads(raw)
            capabilities = parsed.get("capabilities")
            if not isinstance(capabilities, list):
                raise ValueError(f"Malformed shape: {parsed}")
            capabilities = [
                str(c).strip().lower() for c in capabilities if str(c).strip()
            ]
            if not capabilities:
                raise ValueError("Empty capabilities list")
            return capabilities
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            continue

    assert last_error is not None
    raise RuntimeError(
        f"Failed to decompose goal after 3 attempts: {last_error}"
    )


if __name__ == "__main__":
    # Manual smoke test — no Supabase needed, just confirms the Groq call
    # and JSON parsing work end to end.
    test_goal = "Build an AI accountant that reads invoices and updates a spreadsheet"
    result = decompose_goal(test_goal)
    print(json.dumps(result, indent=2))