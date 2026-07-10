-- MCP Intelligence Platform: registry table
-- Run this once in the Supabase SQL editor (or via `supabase db push`).

create extension if not exists pgcrypto;

create table if not exists mcp_registry (
  id uuid primary key default gen_random_uuid(),
  repo_full_name text unique not null,      -- e.g. "owner/mcp-weather"
  name text not null,
  description text,
  readme_excerpt text,                       -- first ~2000 chars of README
  stars int default 0,
  open_issues int default 0,
  last_commit_at timestamptz,
  topics text[] default '{}',
  mcp_type text,                              -- 'server' | 'client' | 'tool'
  capability_tags text[] default '{}',        -- LLM-generated at ingest time
  summary text,                               -- LLM-generated 1-2 sentence summary
  fetched_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Wrapper function so the GIN index below can rely on an explicitly
-- IMMUTABLE function. Postgres won't infer immutability across a chain
-- of coalesce/array_to_string/to_tsvector calls used directly in an
-- index expression, even though the result is deterministic.
create or replace function mcp_registry_tsvector(
  description text,
  summary text,
  capability_tags text[],
  topics text[]
)
returns tsvector as $$
  select to_tsvector(
    'english',
    coalesce(description, '') || ' ' ||
    coalesce(summary, '') || ' ' ||
    array_to_string(capability_tags, ' ') || ' ' ||
    array_to_string(topics, ' ')
  );
$$ language sql immutable;

-- Full text search index across the fields we match capabilities against
create index if not exists mcp_registry_search_idx
  on mcp_registry
  using gin (
    mcp_registry_tsvector(description, summary, capability_tags, topics)
  );

-- Keep updated_at fresh on every upsert
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_mcp_registry_updated_at on mcp_registry;
create trigger trg_mcp_registry_updated_at
  before update on mcp_registry
  for each row execute function set_updated_at();

-- RPC used by app/db/client.py::search_candidates.
-- websearch_to_tsquery handles natural-language-ish input (multi-word
-- capability phrases) more gracefully than plainto_tsquery.
create or replace function search_mcp_registry(query_text text, match_limit int)
returns setof mcp_registry as $$
  select *
  from mcp_registry
  where mcp_registry_tsvector(description, summary, capability_tags, topics)
        @@ websearch_to_tsquery('english', query_text)
  order by ts_rank(
    mcp_registry_tsvector(description, summary, capability_tags, topics),
    websearch_to_tsquery('english', query_text)
  ) desc
  limit match_limit;
$$ language sql stable;
