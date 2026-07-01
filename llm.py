"""
Thin LLM wrapper over any OpenAI-compatible endpoint.

Set these env vars on your HF Space (Settings -> Variables and secrets):
    LLM_API_KEY   your key            (secret)
    LLM_BASE_URL  https://api.openai.com/v1   (or Groq/Together/HF router/Ollama)
    LLM_MODEL     gpt-4o-mini         (or llama-3.3-70b, etc.)

If no key is set, llm_available() returns False and the agent falls back to a
fully deterministic pipeline -- so the Space still works for grading offline.
"""
from __future__ import annotations
import os

MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
_client = None


def llm_available() -> bool:
    return bool(os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"))


def get_client():
    global _client
    if _client is None and llm_available():
        from openai import OpenAI
        _client = OpenAI(
            api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        )
    return _client
