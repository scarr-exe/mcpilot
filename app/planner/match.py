"""
For each decomposed capability, finds candidate MCP servers from the
registry via Supabase full-text search (app/db/client.py::search_candidates,
which calls the search_mcp_registry RPC).

This is a thin, deterministic layer — no LLM calls here. The LLM already
did its job in decompose.py; this step is pure retrieval.
"""
from __future__ import annotations

from typing import Any

from app.config import settings
from app.db.client import search_candidates


def match_capabilities(capabilities: list[str]) -> dict[str, list[dict[str, Any]]]:
    """
    Returns {capability: [candidate_row, ...]} for each capability,
    querying up to settings.MATCH_CANDIDATES_PER_CAPABILITY rows per
    capability from the registry.
    """
    results: dict[str, list[dict[str, Any]]] = {}
    for capability in capabilities:
        # Replace hyphens with spaces so "web-search" matches repos
        # tagged/described with either "web-search" or "web search"
        query_text = capability.replace("-", " ")
        candidates = search_candidates(
            query_text, limit=settings.MATCH_CANDIDATES_PER_CAPABILITY
        )
        results[capability] = candidates
    return results


if __name__ == "__main__":
    import json

    sample_capabilities = ["ocr", "database", "web-scraping"]
    matches = match_capabilities(sample_capabilities)
    for cap, candidates in matches.items():
        print(f"\n{cap}: {len(candidates)} candidates")
        for c in candidates[:3]:
            print(f"  - {c['repo_full_name']} ({c.get('stars', 0)}★)")