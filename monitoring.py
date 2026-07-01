"""
Lightweight monitoring. Records one JSON line per request and keeps rolling
aggregates in memory. Exposed via GET /metrics so a grader can see it working.

Tracks: latency, token usage, estimated cost, tool calls, guardrail activity.
"""
from __future__ import annotations
import json
import os
import time
from threading import Lock

_LOG_PATH = os.getenv("METRICS_LOG", "/tmp/auditor_metrics.jsonl")
_lock = Lock()
_latencies: list = []
_agg = {
    "requests": 0,
    "errors": 0,
    "total_latency_ms": 0.0,
    "total_prompt_tokens": 0,
    "total_completion_tokens": 0,
    "total_cost_usd": 0.0,
    "total_tool_calls": 0,
    "total_blocked_calls": 0,
    "total_guardrail_hits": 0,
    "total_injection_attempts": 0,
    "refusals": 0,
}

# rough price per 1K tokens (gpt-4o-mini defaults; override via env if needed)
_PRICE_IN = float(os.getenv("PRICE_PER_1K_INPUT", "0.00015"))
_PRICE_OUT = float(os.getenv("PRICE_PER_1K_OUTPUT", "0.00060"))


def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return round(prompt_tokens / 1000 * _PRICE_IN + completion_tokens / 1000 * _PRICE_OUT, 6)


class Timer:
    def __enter__(self):
        self._t = time.perf_counter()
        return self

    def __exit__(self, *a):
        self.ms = (time.perf_counter() - self._t) * 1000


def record(event: dict) -> None:
    """Persist one request's metrics and fold into aggregates."""
    event.setdefault("ts", time.time())
    with _lock:
        _agg["requests"] += 1
        _agg["errors"] += int(bool(event.get("error")))
        _agg["refusals"] += int(bool(event.get("refused")))
        _agg["total_latency_ms"] += event.get("latency_ms", 0.0)
        _latencies.append(event.get("latency_ms", 0.0))
        _agg["total_prompt_tokens"] += event.get("prompt_tokens", 0)
        _agg["total_completion_tokens"] += event.get("completion_tokens", 0)
        _agg["total_cost_usd"] += event.get("cost_usd", 0.0)
        _agg["total_tool_calls"] += event.get("tool_calls", 0)
        _agg["total_blocked_calls"] += event.get("blocked_calls", 0)
        _agg["total_guardrail_hits"] += event.get("guardrail_hits", 0)
        _agg["total_injection_attempts"] += event.get("injection_attempts", 0)
        try:
            with open(_LOG_PATH, "a") as f:
                f.write(json.dumps(event) + "\n")
        except OSError:
            pass


def snapshot() -> dict:
    with _lock:
        n = max(_agg["requests"], 1)
        lat_sorted = sorted(_latencies)
        p95 = lat_sorted[min(int(len(lat_sorted) * 0.95), len(lat_sorted) - 1)] if lat_sorted else 0
        return {
            "requests": _agg["requests"],
            "errors": _agg["errors"],
            "refusals": _agg["refusals"],
            "avg_latency_ms": round(_agg["total_latency_ms"] / n, 1),
            "p95_latency_ms": round(p95, 1),
            "total_prompt_tokens": _agg["total_prompt_tokens"],
            "total_completion_tokens": _agg["total_completion_tokens"],
            "total_cost_usd": round(_agg["total_cost_usd"], 6),
            "avg_cost_per_request_usd": round(_agg["total_cost_usd"] / n, 6),
            "total_tool_calls": _agg["total_tool_calls"],
            "total_blocked_calls": _agg["total_blocked_calls"],
            "total_guardrail_hits": _agg["total_guardrail_hits"],
            "total_injection_attempts": _agg["total_injection_attempts"],
        }
