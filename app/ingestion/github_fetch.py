"""
Pulls real, live metadata about MCP servers from GitHub.

Two discovery sources, combined and deduplicated:
  1. GitHub code search for repos tagged with MCP-related topics
  2. The official modelcontextprotocol/servers README, which lists
     both official and community servers (many of which don't self-tag
     with a "mcp-server" topic, so relying on search alone misses them)

This is the module that makes the "ranking" claim defensible later —
everything it returns is a real, timestamped, publicly verifiable metric.
"""
from __future__ import annotations

import base64
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings

GITHUB_API = "https://api.github.com"
SEARCH_TOPICS = ["mcp-server", "model-context-protocol"]
OFFICIAL_LIST_REPO = "modelcontextprotocol/servers"


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
    return headers


def _get(client: httpx.Client, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
    """
    GET with manual retry: only retries on 5xx (server-side) or network
    errors. 4xx errors (404 not found, 403/429 rate limited) fail fast —
    retrying those immediately just burns quota or wastes time, and the
    caller already has logic to handle them (skip, fallback, etc.).
    """
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            response = client.get(url, headers=_headers(), params=params)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            if e.response.status_code < 500:
                raise
            last_exc = e
        except httpx.RequestError as e:
            last_exc = e
        if attempt < 2:
            time.sleep(2 ** attempt)
    assert last_exc is not None
    raise last_exc


def search_repos_by_topic(client: httpx.Client, topic: str, per_page: int = 50) -> list[dict[str, Any]]:
    """GitHub search API: repos tagged with a given topic, sorted by stars."""
    response = _get(
        client,
        f"{GITHUB_API}/search/repositories",
        params={"q": f"topic:{topic}", "sort": "stars", "order": "desc", "per_page": per_page},
    )
    return response.json().get("items", [])


def fetch_official_server_list(client: httpx.Client) -> list[str]:
    """
    Parses the modelcontextprotocol/servers README for linked repos.
    Returns a list of "owner/repo" strings.
    """
    response = _get(client, f"{GITHUB_API}/repos/{OFFICIAL_LIST_REPO}/readme")
    content = base64.b64decode(response.json()["content"]).decode("utf-8", errors="ignore")

    # Matches github.com/<owner>/<repo> links anywhere in the README
    pattern = r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)"
    non_repo_paths = {
        "orgs", "sponsors", "marketplace", "search", "topics", "features",
        "about", "pricing", "contact", "apps", "settings", "notifications",
        "issues", "pulls", "codespaces", "collections",
    }
    found = set()
    for owner, repo in re.findall(pattern, content):
        repo = repo.rstrip(")./")
        if owner.lower() in non_repo_paths:
            continue
        if owner.lower() == "modelcontextprotocol" and repo.lower() == "servers":
            continue
        found.add(f"{owner}/{repo}")
    return sorted(found)


def fetch_repo_metadata(client: httpx.Client, full_name: str) -> dict[str, Any] | None:
    """Fetch core repo metadata (stars, issues, last commit, topics, description)."""
    try:
        repo_resp = _get(client, f"{GITHUB_API}/repos/{full_name}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return None
        raise
    repo = repo_resp.json()

    try:
        commits_resp = _get(client, f"{GITHUB_API}/repos/{full_name}/commits", params={"per_page": 1})
        last_commit_at = commits_resp.json()[0]["commit"]["committer"]["date"]
    except (httpx.HTTPStatusError, IndexError, KeyError):
        last_commit_at = repo.get("pushed_at")

    readme_excerpt = _fetch_readme_excerpt(client, full_name)

    return {
        "repo_full_name": repo["full_name"],
        "name": repo["name"],
        "description": repo.get("description") or "",
        "readme_excerpt": readme_excerpt,
        "stars": repo.get("stargazers_count", 0),
        "open_issues": repo.get("open_issues_count", 0),
        "last_commit_at": last_commit_at,
        "topics": repo.get("topics", []),
        "mcp_type": _guess_mcp_type(repo.get("description") or "", repo.get("topics", [])),
    }


def _fetch_readme_excerpt(client: httpx.Client, full_name: str, max_chars: int = 2000) -> str:
    try:
        response = _get(client, f"{GITHUB_API}/repos/{full_name}/readme")
        content = base64.b64decode(response.json()["content"]).decode("utf-8", errors="ignore")
        return content[:max_chars]
    except httpx.HTTPStatusError:
        return ""


def _guess_mcp_type(description: str, topics: list[str]) -> str:
    text = (description + " " + " ".join(topics)).lower()
    if "client" in text:
        return "client"
    if "tool" in text and "server" not in text:
        return "tool"
    return "server"


def discover_all() -> list[dict[str, Any]]:
    """
    Full discovery run: combines topic search + official README list,
    dedupes, and fetches full metadata for each unique repo.
    """
    with httpx.Client(timeout=20.0) as client:
        candidates: set[str] = set()

        for topic in SEARCH_TOPICS:
            for repo in search_repos_by_topic(client, topic):
                candidates.add(repo["full_name"])

        for full_name in fetch_official_server_list(client):
            candidates.add(full_name)

        results = []
        skipped = 0
        for full_name in sorted(candidates):
            try:
                metadata = fetch_repo_metadata(client, full_name)
            except httpx.HTTPStatusError as e:
                skipped += 1
                status = e.response.status_code
                if status in (403, 429):
                    print(f"  rate limited on {full_name}, skipping ({e})")
                else:
                    print(f"  error fetching {full_name}: {status}, skipping")
                continue
            if metadata:
                results.append(metadata)

        if skipped:
            print(f"Skipped {skipped} repos due to errors/rate limits. "
                  f"Set GITHUB_TOKEN in .env to raise the limit from 60/hr to 5,000/hr.")

        return results


if __name__ == "__main__":
    entries = discover_all()
    print(f"Discovered {len(entries)} MCP repos at {datetime.now(timezone.utc).isoformat()}")
    for e in entries[:10]:
        print(f"  {e['repo_full_name']} — {e['stars']}★")