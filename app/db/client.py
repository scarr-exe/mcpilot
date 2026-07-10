"""
Supabase client singleton + thin helper functions used by both the
ingestion pipeline and the planner (query-time matching).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from supabase import create_client, Client

from app.config import settings

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    return _client


def upsert_mcp_entry(entry: dict[str, Any]) -> None:
    """
    Upsert a single MCP registry row, keyed on repo_full_name.
    Called by the ingestion pipeline, one row at a time.
    """
    entry = {**entry, "fetched_at": datetime.now(timezone.utc).isoformat()}
    get_client().table("mcp_registry").upsert(
        entry, on_conflict="repo_full_name"
    ).execute()


def search_candidates(query_text: str, limit: int) -> list[dict[str, Any]]:
    """
    Full-text search against description/summary/tags/topics.
    Uses Postgres websearch_to_tsquery via an RPC function (see
    app/db/schema.sql companion function below) so we get proper ranking
    without pulling embeddings into scope.
    """
    client = get_client()
    response = client.rpc(
        "search_mcp_registry",
        {"query_text": query_text, "match_limit": limit},
    ).execute()
    return response.data or []


def fetch_all_repo_names() -> set[str]:
    """Used by ingestion to know which rows already exist (for logging/diffing)."""
    client = get_client()
    response = client.table("mcp_registry").select("repo_full_name").execute()
    return {row["repo_full_name"] for row in (response.data or [])}
