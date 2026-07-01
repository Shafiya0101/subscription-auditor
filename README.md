---
title: Subscription Money-Leak Auditor
emoji: 💸
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Subscription Money-Leak Auditor

🔗 **Live app:** https://shafiya1234-subscription-auditor.hf.space
📄 API docs (Swagger): https://shafiya1234-subscription-auditor.hf.space/docs

An agent that reads a pasted bank statement, finds recurring subscriptions,
resolves cryptic merchant names, totals the **annual** cost, and flags charges
worth reviewing. Built for the `lab_04_production_surete` deliverable:
agent + FastAPI on HuggingFace Spaces, ≥2 tools, guardrails, eval, monitoring.

## Why an agent and not just a chatbot
A plain LLM asked "audit my statement" will *guess* — inventing charges and
mis-adding totals, because it predicts text rather than computing. Here the LLM
**orchestrates** and **explains**, but every number comes from a deterministic
tool run on the user's real data. Chatbot guesses; agent verifies.

## Architecture (ReAct: Thought → Action → Observation)
```
statement text
   │
   ▼  INPUT VALIDATION: mask PII (cards/IBANs) · detect prompt injection · refuse non-statements
parse → transactions      (LLM parser if key set, else regex; regex used by eval)
   │
   ▼  ReAct LOOP  (LLM planner + 2 tools + executor, max 8 steps)
   │    guardrails in-loop: tool allow-list · anti-loop · untrusted-data tagging
   ├── TOOL 1  resolve_merchant(raw)        "SQSP*INV 88213" → Squarespace / software
   └── TOOL 2  detect_recurring_charges()   cadence, monthly+annual cost, review flags
   │
   ▼  OUTPUT VALIDATION: grounding (drop merchants absent from the statement)
   ▼  SELF-CRITIQUE: reject a hijacked/ungrounded summary → regenerate from tool data
   ▼  OBSERVABILITY: ReAct trace · latency/p95 · tokens/cost · blocked calls · injection flags
structured audit + human summary
```

Every number comes from a deterministic tool; the LLM orchestrates and explains. See `REPORT.md` for the full mapping to the four course sessions (PEAS, ReAct, guardrail taxonomy, prompt injection, evaluation, deployment).

## Endpoints
| method | path | purpose |
|--------|------|---------|
| GET  | `/`        | minimal demo page (paste + audit) |
| POST | `/audit`   | `{"statement": "..."}` → full audit JSON |
| GET  | `/health`  | liveness + whether an LLM key is connected |
| GET  | `/metrics` | monitoring aggregates |

## Run locally
```bash
pip install -r requirements.txt
uvicorn app:app --port 7860
# open http://localhost:7860
```

## Deploy to HuggingFace Spaces
1. Create a new Space → **Docker** (blank).
2. Upload every file in this folder (keep the structure).
3. Space **Settings → Variables and secrets**: add `LLM_API_KEY` (secret) and,
   if not OpenAI, `LLM_BASE_URL` + `LLM_MODEL`. *Optional* — it runs without them.
4. The Space builds from the `Dockerfile` and serves on port 7860.

## Run the eval
```bash
python eval/run_eval.py
```
Reproducible without an API key (runs the deterministic path).

## Privacy
Statements are processed in-memory for the request only and never persisted.
Card numbers and IBANs are masked before any processing, including before the LLM.
Educational tool, not financial advice.
