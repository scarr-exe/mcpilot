"""
Full ingestion pipeline: discover MCP repos on GitHub, tag each one with
capability_tags + summary via Groq, upsert into Supabase.

Usage:
    python -m app.ingestion.run_ingestion            # skip already-tagged repos
    python -m app.ingestion.run_ingestion --force     # retag everything

This is meant to be run manually / on a schedule (e.g. weekly), NOT on
every /plan request — that's what keeps the API fast and cheap.
"""
from __future__ import annotations

import sys
import time

from app.db.client import fetch_tagged_repo_names, upsert_mcp_entry
from app.ingestion.github_fetch import discover_all
from app.ingestion.tag_generator import generate_tags_and_summary


def run(force: bool = False) -> None:
    print("Step 1/3: discovering MCP repos on GitHub...")
    entries = discover_all()
    print(f"  found {len(entries)} repos")

    already_tagged = set() if force else fetch_tagged_repo_names()
    if already_tagged:
        print(f"  {len(already_tagged)} already tagged, will skip those (use --force to retag)")

    print("Step 2/3: tagging + upserting...")
    tagged, skipped, failed = 0, 0, 0

    for i, entry in enumerate(entries, start=1):
        repo_name = entry["repo_full_name"]

        if repo_name in already_tagged:
            skipped += 1
            continue

        try:
            tags_and_summary = generate_tags_and_summary(entry)
        except RuntimeError as e:
            print(f"  [{i}/{len(entries)}] FAILED to tag {repo_name}: {e}")
            failed += 1
            continue

        full_entry = {**entry, **tags_and_summary}
        try:
            upsert_mcp_entry(full_entry)
        except Exception as e:
            print(f"  [{i}/{len(entries)}] FAILED to upsert {repo_name}: {e}")
            failed += 1
            continue

        tagged += 1
        print(f"  [{i}/{len(entries)}] tagged + upserted: {repo_name} "
              f"({', '.join(tags_and_summary['capability_tags'][:4])})")

        # Small delay to stay comfortably under Groq's rate limits
        time.sleep(0.3)

    print("Step 3/3: done.")
    print(f"  tagged+upserted: {tagged}, skipped (already tagged): {skipped}, failed: {failed}")


if __name__ == "__main__":
    force_flag = "--force" in sys.argv
    run(force=force_flag)