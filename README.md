# MCPilot

**The capability planner for AI agents.**

MCPilot is an Agent Service Provider (ASP) built for the OKX AI Genesis Hackathon. It solves a problem that gets harder as the MCP (Model Context Protocol) ecosystem grows: given a goal in plain English, which MCP servers should an agent actually use, in what order, and why?

Instead of manually searching registries and guessing at reliability, MCPilot decomposes a goal into technical capabilities, discovers real MCP servers from live GitHub data, ranks them with a transparent formula, explains every recommendation in plain language, and assembles the whole thing into an ordered execution workflow — plus a high-level architecture sketch for the agent that would run it.

**Live MCP endpoint:** `https://mcpilot-production.up.railway.app/mcp`

---

## The Problem

The MCP ecosystem has gone from a handful of servers to hundreds, growing weekly. That creates a new bottleneck: discovering the right capability is now harder than using it once you've found it. Developers and agents alike are stuck with the same unanswered questions:

- Which MCP server should I use for this?
- Are there better alternatives?
- Which combination of MCPs actually solves my task?
- Why is one recommended over another?
- What should the surrounding agent architecture even look like?

MCPilot answers all five in a single call.

---

## How It Works

```
User / AI Agent
      ↓
   "Build an AI accountant"
      ↓
┌─────────────────────────────────────────────┐
│ 1. Goal Decomposition        (Groq LLM)      │
│ 2. Capability → MCP Matching (Supabase FTS)  │
│ 3. Deterministic Ranking     (real GitHub data)│
│ 4. Explanation Generation    (Groq LLM)      │
│ 5. Workflow Assembly         (Groq LLM)      │
│ 6. Architecture Generation   (Groq LLM)      │
└─────────────────────────────────────────────┘
      ↓
Structured JSON: capabilities, ranked recommendations,
ordered workflow, agent architecture sketch
```

No frontend. The product *is* the MCP tool — OKX.AI and other agents are the client, calling a single `plan` tool with a natural-language goal.

---

## What Makes the Ranking Trustworthy

Most "AI recommends a tool" systems either hand-wave a plausibility score or let an LLM invent metrics like "community rating" out of thin air. MCPilot doesn't do either.

**Discovery is real.** Every MCP in the registry comes from live GitHub data — the official `modelcontextprotocol/servers` list plus topic-tagged repo search — pulled and cached via `app/ingestion/github_fetch.py`. Nothing is hand-curated or invented.

**Ranking is deterministic.** The composite score is a fixed formula over real, verifiable metadata, computed the same way every time for the same inputs:

```
score = (stars_score        × 0.4)
      + (recency_score      × 0.3)
      + (issue_health_score × 0.3)
```

- `stars_score` — log-scaled GitHub stars, capped so one mega-popular repo can't totally dominate
- `recency_score` — exponential decay based on days since last commit (180-day half-life)
- `issue_health_score` — inverse of open issue count, capped at 100

See `app/planner/rank.py` for the exact implementation and tunable weights (in `app/config.py`).

**The LLM only narrates, never invents.** `app/planner/explain.py` gives the LLM the precomputed score breakdown and real metadata, and explicitly instructs it not to reference metrics it wasn't given. If a candidate's data is sparse, the explanation says so plainly instead of filling in confident-sounding filler.

**Unmatched capabilities are surfaced, not hidden.** If a decomposed capability has zero real matches in the registry, it shows up in an explicit `unmatched_capabilities` field rather than silently vanishing from the response.

This is the one place MCPilot is candid about a limitation: the *ranking and matching* are fully deterministic and reproducible, but the *decomposition, explanation, workflow, and architecture* steps are LLM-generated and can vary between runs, same as any agent reasoning over natural language would.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python, FastAPI |
| MCP layer | FastMCP (wraps the FastAPI app directly) |
| Database | Supabase (Postgres, full-text search via a `tsvector` RPC) |
| LLM | Groq (`llama-3.3-70b-versatile`) — decomposition, explanation, workflow, architecture |
| Registry source | GitHub REST API — live, public, no scraping of registries without APIs |
| Deployment | Railway, HTTPS by default |
| Testing | MCP Inspector (official) |

---

## Repo Structure

```
mcp-intelligence-platform/
├── app/
│   ├── main.py                # FastAPI app, POST /plan
│   ├── mcp_server.py          # FastMCP wrapper (stdio locally, HTTP in production)
│   ├── config.py              # settings, ranking weights
│   ├── models.py              # Pydantic request/response schemas
│   ├── db/
│   │   ├── client.py          # Supabase client + search helpers
│   │   └── schema.sql         # registry table + full-text search RPC
│   ├── llm/
│   │   └── client.py          # shared Groq client
│   ├── ingestion/
│   │   ├── github_fetch.py    # live MCP discovery from GitHub
│   │   ├── tag_generator.py   # LLM-generated capability tags + summary
│   │   └── run_ingestion.py   # orchestrates discovery → tagging → upsert
│   └── planner/
│       ├── decompose.py       # goal → capabilities (LLM)
│       ├── match.py           # capabilities → candidate MCPs (Supabase FTS)
│       ├── rank.py            # deterministic composite scoring
│       ├── explain.py         # grounded, data-cited explanations (LLM)
│       ├── workflow.py        # ordered execution pipeline (LLM, validated against real MCPs)
│       ├── architecture.py    # high-level agent architecture sketch (LLM)
│       └── pipeline.py        # ties every stage together into one call
├── railway.json
├── requirements.txt
└── .env.example
```

---

## Setup

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
GROQ_API_KEY=your-groq-key
GITHUB_TOKEN=your-github-token   # raises rate limit 60/hr → 5,000/hr
```

Run `app/db/schema.sql` in the Supabase SQL editor, then populate the registry:

```bash
python -m app.ingestion.run_ingestion
```

This discovers MCP servers from GitHub, tags each with capabilities via Groq, and upserts into Supabase. Takes a few minutes for ~100 repos. Rerun anytime — already-tagged repos are skipped by default (`--force` to retag everything).

---

## Running Locally

**As a REST API:**
```bash
python -m app.main
```
Visit `http://localhost:8000/docs` for interactive testing, or `POST /plan`:
```json
{"goal": "build a web scraping agent that saves results to a database"}
```

**As an MCP server (stdio, for MCP Inspector):**
```bash
python -m app.mcp_server
```
Or test directly:
```bash
npx @modelcontextprotocol/inspector python -m app.mcp_server
```

**Running the full pipeline standalone (no server):**
```bash
python -m app.planner.pipeline
```

Each planner stage can also be run and inspected independently — see the `if __name__ == "__main__":` block at the bottom of `decompose.py`, `match.py`, `rank.py`, `explain.py`, `workflow.py`, and `architecture.py`.

---

## API Reference

### `POST /plan`

**Request:**
```json
{ "goal": "string, required" }
```

**Response:**
```json
{
  "goal": "string",
  "capabilities": ["string", ...],
  "unmatched_capabilities": ["string", ...],
  "recommendations": {
    "capability_name": [
      {
        "repo_full_name": "owner/repo",
        "name": "string",
        "summary": "string",
        "stars": 0,
        "open_issues": 0,
        "last_commit_at": "ISO8601 timestamp",
        "capability_tags": ["string", ...],
        "score": 0.0,
        "score_breakdown": {
          "stars_score": 0.0,
          "recency_score": 0.0,
          "issue_health_score": 0.0
        },
        "explanation": "string"
      }
    ]
  },
  "workflow": [
    {
      "step": 1,
      "capability": "string",
      "mcp": "owner/repo",
      "reason": "string"
    }
  ],
  "architecture": {
    "reasoning_layer": "string",
    "memory": "string",
    "external_tools": "string",
    "notes": "string"
  }
}
```

### As an MCP tool

Once deployed, the same functionality is exposed as an MCP tool (`plan_plan_post`) reachable at `https://your-domain/mcp` via streamable-HTTP transport — no separate integration needed, FastMCP generates it directly from the FastAPI route.

---

## Deployment

Deployed on Railway with HTTPS provided automatically. `app/mcp_server.py` switches transport based on environment:

- No `MCP_TRANSPORT` set → stdio (local dev, MCP Inspector)
- `MCP_TRANSPORT=http` → streamable-HTTP on `$PORT` (production)

Required environment variables in production: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `GROQ_API_KEY`, `GITHUB_TOKEN`, `MCP_TRANSPORT=http`.

---

## Known Limitations (MVP Scope)

Deliberately out of scope for the hackathon build, documented here rather than glossed over:

- **Single registry source.** Discovery currently covers GitHub-hosted MCP servers only. Smithery, Glama, and other registries aren't yet integrated — noted as a natural next step, not hidden as if GitHub were exhaustive.
- **No automatic execution.** MCPilot plans workflows, it doesn't invoke the recommended MCPs itself. That's an intentional boundary, not a missing feature — planning and execution are different concerns.
- **No compatibility validation.** The workflow step doesn't verify that one MCP's output schema actually matches the next step's expected input. Flagged as the most valuable near-term addition.
- **Non-deterministic reasoning layers.** Decomposition, explanation, workflow ordering, and architecture generation are LLM calls and can vary run-to-run for the same goal, even though matching and ranking are fully deterministic.
- **Registry coverage gaps are real and surfaced, not hidden.** Niche domains (e.g. tax filing, industry-specific compliance) may have few or no matching MCPs today — the `unmatched_capabilities` field makes this explicit instead of forcing a weak match.

---

## Roadmap (Post-Hackathon)

- Multi-registry discovery (Smithery, Glama, mcp.so)
- MCP-to-MCP compatibility/schema validation
- Cost and latency estimation per workflow
- Live orchestration/execution mode, not just planning
- Performance benchmarking across MCPs solving the same capability

---

## License

MIT