"""
Takes raw GitHub metadata for one MCP repo and asks the LLM (via Groq)
to produce:
  - capability_tags: normalized, lowercase tags describing what this
    MCP actually does (used for full-text matching against user goals)
  - summary: a 1-2 sentence plain-English description

This runs ONCE per repo at ingestion time, not per user request — keeps
the /plan endpoint fast and keeps LLM costs bounded by registry size,
not by traffic.
"""
from __future__ import annotations

import json
from typing import Any

from app.config import settings
from app.llm.client import get_groq_client


SYSTEM_PROMPT = """You are a capability tagging engine for an MCP (Model \
Context Protocol) server registry. Given a repo's name, description, \
topics, and a README excerpt, output ONLY a JSON object with this exact \
shape, no other text:

{
  "capability_tags": ["tag1", "tag2", ...],
  "summary": "1-2 sentence plain-English description of what this MCP does"
}

Rules for capability_tags:
- 3 to 8 tags
- lowercase, single words or short hyphenated phrases (e.g. "ocr", \
"web-search", "database", "file-system", "spreadsheet", "translation")
- describe CAPABILITIES the MCP provides, not the implementation language \
or framework
- if the README/description is too sparse to tell, make your best \
inference from the name and topics rather than leaving tags empty

Rules for summary:
- factual, based only on the provided text, no marketing language
- if you genuinely cannot tell what it does, say so plainly rather than \
guessing confidently
"""


def _build_user_prompt(entry: dict[str, Any]) -> str:
    return (
        f"Repo: {entry.get('repo_full_name', '')}\n"
        f"Name: {entry.get('name', '')}\n"
        f"Description: {entry.get('description', '') or '(none provided)'}\n"
        f"Topics: {', '.join(entry.get('topics', [])) or '(none)'}\n"
        f"README excerpt:\n{entry.get('readme_excerpt', '')[:1500] or '(none)'}"
    )


def generate_tags_and_summary(entry: dict[str, Any]) -> dict[str, Any]:
    """
    Returns {"capability_tags": [...], "summary": "..."}.
    Raises on repeated malformed output — caller decides whether to skip
    or abort the whole ingestion run.
    """
    client = get_groq_client()
    last_error: Exception | None = None

    for attempt in range(3):
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(entry)},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw = response.choices[0].message.content
        try:
            parsed = json.loads(raw)
            tags = parsed.get("capability_tags")
            summary = parsed.get("summary")
            if not isinstance(tags, list) or not isinstance(summary, str):
                raise ValueError(f"Malformed shape: {parsed}")
            tags = [str(t).strip().lower() for t in tags if str(t).strip()]
            if not tags or not summary.strip():
                raise ValueError(f"Empty tags or summary: {parsed}")
            return {"capability_tags": tags, "summary": summary.strip()}
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            continue

    assert last_error is not None
    raise RuntimeError(
        f"Failed to generate valid tags for {entry.get('repo_full_name')} "
        f"after 3 attempts: {last_error}"
    )


if __name__ == "__main__":
    # Quick manual test against a single hand-built entry, no GitHub or
    # Supabase calls needed — useful for verifying the Groq key works.
    sample = {
        "repo_full_name": "example/mcp-weather",
        "name": "mcp-weather",
        "description": "An MCP server that provides current weather and forecasts",
        "topics": ["mcp-server", "weather", "api"],
        "readme_excerpt": "This server exposes tools to fetch current weather "
        "conditions and 5-day forecasts for any city using the OpenWeather API.",
    }
    result = generate_tags_and_summary(sample)
    print(json.dumps(result, indent=2))