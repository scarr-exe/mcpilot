"""
Shared Groq client singleton. Both the ingestion pipeline (tagging) and
the planner (decomposition, explanation, workflow, architecture) call
through here so there's one place that owns the client lifecycle.
"""
from __future__ import annotations

from groq import Groq

from app.config import settings

_client: Groq | None = None


def get_groq_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client