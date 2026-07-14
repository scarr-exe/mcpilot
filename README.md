# MCPilot

**The capability planner for AI agents.**

MCPilot is an Agent Service Provider (ASP) built for the OKX AI Genesis Hackathon. It solves a problem that gets harder as the MCP (Model Context Protocol) ecosystem grows: given a goal in plain English, which MCP servers should an agent actually use, in what order, and why?

Instead of manually searching registries and guessing at reliability, MCPilot decomposes a goal into technical capabilities, discovers real MCP servers from live GitHub data, ranks them with a transparent formula, explains every recommendation in plain language, and assembles the whole thing into an ordered execution workflow — plus a high-level architecture sketch for the agent that would run it.

**Live MCP endpoint:** `https://mcpilot-production.up.railway.app/mcp`

**Live REST API** (used by the demo landing page): `https://mcpilot-production-ac81.up.railway.app`

**OKX.AI listing:** registered as an A2MCP service (Agent ID #5144), submitted for review

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

The product itself needs no frontend — OKX.AI and other agents are the client, calling a single `plan` tool with a natural-language goal over MCP. A separate demo landing page (`web/`) exists purely to make that same pipeline watchable for humans; see [Demo Landing Page](#demo-landing-page) below.

---

## What Makes the Ranking Trustworthy

Most "AI recommends a tool" systems either hand-wave a plausibility score or let an LLM invent metrics like "community rating" out of thin air. MCPilot doesn't do either.

**Discovery is real, and deliberately wide.** Every MCP in the registry comes from live GitHub data, pulled via `app/ingestion/github_fetch.py` through three complementary discovery paths:
- Topic search (`mcp-server`, `model-context-protocol`)
- The official `modelcontextprotocol/servers` list
- Targeted keyword searches (`slack mcp server`, `github mcp server`, `webhook mcp server`, `notification mcp server`, `summarization mcp server`, `pdf mcp server`, `database mcp server`) — added after testing revealed topic search alone misses real servers that exist but weren't tagged with the standard MCP topics on GitHub

Nothing is hand-curated or invented. The keyword list is intentionally treated as a living list — expand it whenever live testing surfaces a capability gap that turns out to be a discovery blind spot rather than a genuine registry gap (see Known Limitations below for how to tell the difference).

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

**Unmatched capabilities are surfaced, not hidden.** If a decomposed capability has zero real matches in the registry, it shows up in an explicit `unmatched_capabilities` field rather than silently vanishing from the response. The demo landing page's "briefing" view surfaces this exact field directly to the user for the same reason.

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
| Deployment | Railway, HTTPS by default — two services from one repo (see Deployment) |
| Demo frontend | Static HTML/CSS/JS (`web/`), no framework, calls the REST API directly |
| Testing | MCP Inspector (official) |

---

## Repo Structure

```
mcp-intelligence-platform/
├── app/
│   ├── main.py                # FastAPI app, POST /plan, CORS enabled for the demo page
│   ├── mcp_server.py          # FastMCP wrapper (stdio locally, HTTP in production)
│   ├── config.py              # settings, ranking weights
│   ├── models.py              # Pydantic request/response schemas
│   ├── db/
│   │   ├── client.py          # Supabase client + search helpers
│   │   └── schema.sql         # registry table + full-text search RPC
│   ├── llm/
│   │   └── client.py          # shared Groq client
│   ├── ingestion/
│   │   ├── github_fetch.py    # live MCP discovery from GitHub (topic + keyword search)
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
├── web/
│   ├── index.html             # demo landing page
│   ├── style.css              # cockpit/HUD visual identity
│   └── app.js                 # hero animation + live /plan demo + briefing renderer
├── railway.json                # build config only — start commands set per-service in Railway UI
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

This discovers MCP servers from GitHub (topic + keyword search), tags each with capabilities via Groq, and upserts into Supabase. Takes a few minutes for ~100-150 repos. Rerun anytime — already-tagged repos are skipped by default (`--force` to retag everything). The registry updates live in Supabase; no redeploy is needed for either Railway service to see new data.

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

**Demo landing page:** open `web/index.html` directly in a browser (no local server needed) — it calls the live deployed REST API. To point it at a local backend instead, change `API_BASE` at the top of `web/app.js`.

Each planner stage can also be run and inspected independently — see the `if __name__ == "__main__":` block at the bottom of `decompose.py`, `match.py`, `rank.py`, `explain.py`, `workflow.py`, and `architecture.py`.

---

## Demo Landing Page

`web/` is a static, framework-free page built purely to make the pipeline watchable — it is **not** part of the ASP submission itself, since OKX.AI and other agents consume MCPilot entirely over MCP, with no frontend required.

- **Hero:** an interactive canvas visualizes the core mechanic directly — scattered, unlabeled nodes (the unmapped MCP ecosystem) resolve into a plotted flight path with lit waypoints, with cursor-reactive parallax and a HUD-style coordinate reticle
- **Stages:** the six real pipeline stages, shown as flight-plan waypoints (`WP-1` through `WP-6`)
- **Live demo:** a goal input that calls the real `/plan` endpoint directly, with two views:
  - **Briefing** — a plain-English readout built entirely from the real `explanation` / `reason` / `notes` text the backend already generates. No extra LLM call, no fabricated summary — it's the actual output, reformatted for reading.
  - **Raw Output** — the actual JSON response
- **Footer:** links to the repo and live MCP endpoint

CORS is enabled on the FastAPI app (`allow_origins=["*"]`) specifically so this static page can call the API cross-origin from a `file://` path with no build step or server required.

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

The same functionality is exposed as an MCP tool (`plan_plan_post`) reachable at `https://mcpilot-production.up.railway.app/mcp` via streamable-HTTP transport — no separate integration needed, FastMCP generates it directly from the FastAPI route. Verified working end-to-end via MCP Inspector and via a live agent (Antigravity) calling it as a configured MCP server.

---

## Deployment

Deployed on Railway, HTTPS provided automatically, as **two services built from the same repo**:

1. **`mcpilot-production`** — runs `python -m app.mcp_server` with `MCP_TRANSPORT=http`. This is the actual ASP endpoint submitted to OKX.AI, serving MCP protocol traffic only at `/mcp`.
2. **`mcpilot-production-ac81`** — runs `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Plain REST API, used exclusively by the demo landing page (`web/`), since FastMCP's `/mcp`-only wrapping doesn't expose browsable REST routes.

`railway.json` intentionally contains no `startCommand` — each service's start command is set independently in its Railway Settings, since both services build from the same `railway.json` and would otherwise be forced to match.

`app/mcp_server.py` switches transport based on environment:
- No `MCP_TRANSPORT` set → stdio (local dev, MCP Inspector)
- `MCP_TRANSPORT=http` → streamable-HTTP on `$PORT` (production)

Required environment variables on **both** services: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `GROQ_API_KEY`, `GITHUB_TOKEN`. Only the MCP service additionally needs `MCP_TRANSPORT=http`.

---

## Known Limitations (MVP Scope)

Deliberately out of scope for the hackathon build, documented here rather than glossed over:

- **Registry coverage depends on discovery breadth, not just registry size.** Early testing showed capabilities like `github-api`, `slack-integration`, and `webhook` returning zero matches — not because no such MCP servers exist, but because topic-only search missed them. Adding targeted keyword searches recovered most of these (a Slack/GitHub-PR-summary goal went from 2/5 matched to 4/5 after widening discovery). This is treated as an ongoing process: a capability showing 0 matches should first be checked against a wider keyword search before being accepted as a genuine gap.
- **Single registry source.** Discovery currently covers GitHub-hosted MCP servers only. Smithery, Glama, and other registries aren't yet integrated — noted as a natural next step, not hidden as if GitHub were exhaustive.
- **No automatic execution.** MCPilot plans workflows, it doesn't invoke the recommended MCPs itself. That's an intentional boundary, not a missing feature — planning and execution are different concerns.
- **No compatibility validation.** The workflow step doesn't verify that one MCP's output schema actually matches the next step's expected input. Flagged as the most valuable near-term addition.
- **Non-deterministic reasoning layers.** Decomposition, explanation, workflow ordering, and architecture generation are LLM calls and can vary run-to-run for the same goal, even though matching and ranking are fully deterministic.
- **Registry coverage gaps are real and surfaced, not hidden.** Niche domains (e.g. tax filing, industry-specific compliance, price-monitoring/alerting) may have few or no matching MCPs today — the `unmatched_capabilities` field makes this explicit instead of forcing a weak match.

---

## Roadmap (Post-Hackathon)

- Multi-registry discovery (Smithery, Glama, mcp.so)
- Automatic keyword-gap detection — flag capabilities with low match rates across multiple test goals and auto-suggest new discovery keywords, rather than relying on manual testing to find blind spots
- MCP-to-MCP compatibility/schema validation
- Cost and latency estimation per workflow
- Live orchestration/execution mode, not just planning
- Performance benchmarking across MCPs solving the same capability

---

## License

MIT
