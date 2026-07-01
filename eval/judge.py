"""
LLM-as-judge (Session 4: exact-match -> LLM-as-judge -> by category).

Exact-match (run_eval.py) checks the numbers. But the human SUMMARY is open-ended,
so a second model grades it against a reference rubric. This is OPTIONAL and only
runs when an LLM key is set, so the main eval stays reproducible offline.

    python eval/judge.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import run_audit  # noqa: E402
from llm import MODEL, get_client, llm_available  # noqa: E402

RUBRIC = (
    "You grade a subscription-audit summary. Score 0-5 on: "
    "(1) does it state the annual recurring total, (2) does it name the top subscriptions, "
    "(3) is it free of invented merchants, (4) is it honest that it sees charges not usage. "
    "Return ONLY JSON: {\"score\": int, \"reason\": str}."
)


def judge_one(statement: str) -> dict:
    result = run_audit(statement)
    summary = result.get("summary", "")
    reference = json.dumps(result.get("totals", {})) + " " + json.dumps(
        [s["merchant"] for s in result.get("subscriptions", [])]
    )
    client = get_client()
    resp = client.chat.completions.create(
        model=MODEL, temperature=0,
        messages=[
            {"role": "system", "content": RUBRIC},
            {"role": "user", "content": f"REFERENCE FACTS: {reference}\n\nSUMMARY TO GRADE:\n{summary}"},
        ],
    )
    raw = resp.choices[0].message.content.strip().strip("`")
    raw = raw[4:] if raw.lower().startswith("json") else raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"score": None, "reason": raw[:200]}


def main():
    if not llm_available():
        print("No LLM key set -> LLM-as-judge skipped. Set LLM_API_KEY to enable.")
        return
    cases = json.load(open(os.path.join(os.path.dirname(__file__), "test_statements.json")))
    detection = [c for c in cases if c.get("type") == "detection"]
    total = 0
    for c in detection:
        g = judge_one(c["statement"])
        print(f"{c['id']:<26} score={g.get('score')}  {g.get('reason','')[:70]}")
        total += g.get("score") or 0
    print(f"\nAverage judge score: {total / max(len(detection),1):.2f} / 5")


if __name__ == "__main__":
    main()
