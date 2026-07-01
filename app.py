"""
FastAPI wrapper around the agent.

Endpoints:
  GET  /          minimal demo page (paste a statement, see the audit)
  POST /audit     {"statement": "..."} -> full audit JSON
  GET  /health    liveness
  GET  /metrics   monitoring aggregates
"""
from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import monitoring
from agent import run_audit
from llm import llm_available

app = FastAPI(title="Subscription Money-Leak Auditor", version="1.0")


class AuditRequest(BaseModel):
    statement: str


@app.post("/audit")
def audit(req: AuditRequest):
    return run_audit(req.statement)


@app.get("/health")
def health():
    return {"status": "ok", "llm_connected": llm_available()}


@app.get("/metrics")
def metrics():
    return monitoring.snapshot()


_DEMO = """<!doctype html><html><head><meta charset="utf-8">
<title>Subscription Auditor</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 16px;color:#1a2233}
 h1{font-size:1.5rem} textarea{width:100%;height:220px;font-family:ui-monospace,monospace;font-size:13px;padding:10px;border:1px solid #cbd2dc;border-radius:8px}
 button{background:#16233d;color:#fff;border:0;padding:10px 18px;border-radius:8px;font-size:15px;cursor:pointer;margin-top:8px}
 pre{background:#0f1626;color:#e6edf7;padding:16px;border-radius:8px;overflow:auto;white-space:pre-wrap}
 .hint{color:#64748b;font-size:13px}
</style></head><body>
<h1>Subscription Money-Leak Auditor</h1>
<p class="hint">Paste an anonymised statement (date &nbsp; description &nbsp; amount per line). Nothing is stored.</p>
<textarea id="s">2026-01-04  NETFLIX.COM           13.49
2026-01-06  SQSP*INV 88213 DUBLIN  17.00
2026-01-09  SPOTIFY P1F3A9         10.99
2026-02-04  NETFLIX.COM           13.49
2026-02-06  SQSP*INV 90114 DUBLIN  17.00
2026-02-09  SPOTIFY P4Z8B2         10.99
2026-01-15  BASIC-FIT PARIS        29.99
2026-02-15  BASIC-FIT PARIS        29.99
2026-01-22  DEEZER PREMIUM         11.99
2026-02-22  DEEZER PREMIUM         11.99
2026-01-30  MONOPRIX PARIS 12      42.10</textarea>
<button onclick="go()">Audit</button>
<pre id="out">Result appears here...</pre>
<script>
async function go(){
 const out=document.getElementById('out'); out.textContent='Analysing...';
 const r=await fetch('/audit',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({statement:document.getElementById('s').value})});
 const d=await r.json();
 if(d.status!=='ok'){out.textContent=d.message||JSON.stringify(d,null,2);return;}
 let t=d.summary+'\\n\\n--- structured ---\\n';
 t+='Annual recurring: '+d.totals.annual_recurring+'  ('+d.totals.monthly_recurring+'/mo)\\n\\n';
 d.subscriptions.forEach(s=>{t+=`• ${s.merchant} — ${s.amount_per_charge} ${s.cadence} → ${s.annual_cost}/yr [${s.confidence}]\\n`});
 if(d.review_flags.length){t+='\\nFlags:\\n';d.review_flags.forEach(f=>t+=' ⚑ '+f.message+'\\n')}
 t+='\\n(latency '+d.monitoring.latency_ms+'ms, cost $'+d.monitoring.estimated_cost_usd+', llm='+d.used_llm+')';
 out.textContent=t;
}
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def home():
    return _DEMO
