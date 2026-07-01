# Deployment guide — Subscription Money-Leak Auditor
Goal: a live HuggingFace Space URL to send your instructor **before Sunday July 5th, 1:00 pm** (hard deadline).

Estimated time: ~15–20 min. No credit card needed.

---

## Step 0 — Download the project
Download `subscription-auditor.zip` and unzip it. You should see 15 items at the top level
(`app.py`, `agent.py`, `tools.py`, `guardrails.py`, `monitoring.py`, `llm.py`,
`Dockerfile`, `requirements.txt`, `README.md`, `REPORT.md`, `.env.example`, and an `eval/` folder).
Keep this structure — do NOT put everything inside a subfolder.

## Step 1 — Get a free LLM key (2 min, recommended)
The Space works with NO key (deterministic fallback), but a key enables the LLM parsing
and the live prompt-injection demo — better for grading.

Free, no card: **Groq**.
1. Go to https://console.groq.com → sign up (email/Google/GitHub).
2. Open **API Keys** → **Create API Key** → copy it (shown once).
Your three values will be:
- `LLM_API_KEY` = the key you just copied
- `LLM_BASE_URL` = `https://api.groq.com/openai/v1`
- `LLM_MODEL` = `llama-3.3-70b-versatile`

(If your course already gave you an OpenAI/other key, use that instead:
base_url `https://api.openai.com/v1`, model `gpt-4o-mini`.)

## Step 2 — Create the Space
1. Go to https://huggingface.co → sign up / log in.
2. Go to https://huggingface.co/new-space.
3. Fill in:
   - **Owner**: you   - **Space name**: e.g. `subscription-auditor`
   - **License**: any (e.g. MIT)
   - **SDK**: **Docker** → **Blank**
   - **Hardware**: CPU basic (free)
   - **Visibility**: **Public**  ← so your instructor can open it
4. Click **Create Space**. An almost-empty repo appears.

## Step 3 — Upload the files
Easiest (no git): on the Space page, **Files** tab → **+ Add file** → **Upload files**.
1. Drag in ALL the top-level files.
2. For the `eval/` folder: drag the folder in, OR create files named
   `eval/run_eval.py`, `eval/judge.py`, `eval/test_statements.json` (the `/` makes the folder).
3. It will ask to overwrite the default `README.md` — say yes (ours has the required
   `sdk: docker` / `app_port: 7860` header).
4. **Commit changes to main**.

The build starts automatically. Watch the **Logs** tab (first build ≈ 2–4 min).
"Running" = success.

## Step 4 — Add your key as a secret
Space **Settings** → **Variables and secrets**:
- **New secret**: name `LLM_API_KEY`, value = your key.
- **New variable**: `LLM_BASE_URL` = `https://api.groq.com/openai/v1`
- **New variable**: `LLM_MODEL` = `llama-3.3-70b-versatile`
The Space restarts. (Skip this to run key-free in deterministic mode.)

## Step 5 — Test it
Two URLs:
- Space page: `https://huggingface.co/spaces/<you>/subscription-auditor`
- Live app:   `https://<you>-subscription-auditor.hf.space`  ← this serves the API

Check:
- Open the live app URL → the demo page loads → click **Audit**.
- `https://<you>-subscription-auditor.hf.space/health` → `{"status":"ok","llm_connected":true}`
- `https://<you>-subscription-auditor.hf.space/docs` → interactive Swagger UI for `POST /audit`.
- `https://<you>-subscription-auditor.hf.space/metrics` → latency/cost/injection counters.

Quick API test from your terminal:
```
curl -X POST https://<you>-subscription-auditor.hf.space/audit \
  -H "Content-Type: application/json" \
  -d '{"statement":"2026-01-04 NETFLIX 13.49\n2026-02-04 NETFLIX 13.49\n2026-01-06 SPOTIFY 10.99\n2026-02-06 SPOTIFY 10.99"}'
```

## Step 6 — Numbers for the report (local, 1 min)
On your laptop, in the unzipped folder:
```
pip install -r requirements.txt
python eval/run_eval.py          # screenshot the precision/recall + injection table
python eval/judge.py             # optional, needs a key set locally
```
Set a key locally first if you want the judge:
```
export LLM_API_KEY=...    LLM_BASE_URL=https://api.groq.com/openai/v1    LLM_MODEL=llama-3.3-70b-versatile
```

## Step 7 — Finalise the mini-report
Open `REPORT.md`, paste your live Space URL at the top, and drop in the eval screenshot.
Export to PDF if your instructor wants a file (or just send REPORT.md).

## Step 8 — Send it (before 1:00 pm Sunday)
Send: the **live app URL**, the **Space page URL**, and `REPORT.md`.
Tip: the free Space sleeps when idle and takes ~30 s to wake. Open your live URL once a
few minutes before you send, so it's warm when the instructor clicks.

---

## Troubleshooting
- **Build failed** → Logs tab. Usually a file wasn't at the repo root, or `eval/` files
  weren't under an `eval/` path. Re-upload with correct paths.
- **404 on the app** → wait for "Running"; use the `*.hf.space` URL, not the `/spaces/` page.
- **`llm_connected:false`** but you set a key → check the secret is named exactly
  `LLM_API_KEY` and the Space restarted.
- **Tool-calling error with Groq** → make sure `LLM_MODEL=llama-3.3-70b-versatile`
  (it supports tool calls). Smaller models may not.
- **Permission error in logs** → the provided Dockerfile already runs as user 1000; make
  sure you uploaded THIS Dockerfile (not a hand-written one).
