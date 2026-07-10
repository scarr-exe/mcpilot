# MCP Intelligence Platform

The capability planner for AI agents — built as an OKX.AI Agent Service Provider (ASP)
for the OKX AI Genesis Hackathon.

## Phase 1 status: Foundation

This phase sets up:
- Project scaffold
- Supabase schema for the MCP registry (`app/db/schema.sql`)
- Supabase client + search helpers (`app/db/client.py`)
- GitHub-based MCP discovery (`app/ingestion/github_fetch.py`)

## Setup

1. `python3 -m venv venv && source venv/bin/activate`
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in:
   - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (from your Supabase project settings)
   - `ANTHROPIC_API_KEY` not required — this project uses Groq instead. Needed starting Phase 2:
     `GROQ_API_KEY` (from console.groq.com)
   - `GITHUB_TOKEN` (a personal access token with no special scopes needed —
     just used to raise the rate limit from 60/hr to 5,000/hr)
4. In the Supabase SQL editor, run the contents of `app/db/schema.sql`
5. Smoke test discovery (no Supabase/Anthropic needed for this step):
   ```
   python -m app.ingestion.github_fetch
   ```
   Should print a count of discovered MCP repos and the top 10 by stars.

## What's next (Phase 2)

- `app/ingestion/tag_generator.py` — LLM pass to generate `capability_tags` + `summary`
- `app/ingestion/run_ingestion.py` — orchestrates discovery → tagging → Supabase upsert
