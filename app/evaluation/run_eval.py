"""
Evaluation harness.

Requires the backend to be running at API_URL (default http://localhost:8000).

Usage:
    python -m app.evaluation.run_eval --url http://localhost:8000

Writes:
    data/evaluation/report.json
"""

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "evaluation"

# Password for all seeded users
DEMO_PASSWORD = "password123"

EMAIL_BY_ROLE = {
    "employee": "alice.johnson@meridianglobal.example",
    "manager": "bob.smith@meridianglobal.example",
    "hr": "meera.iyer@meridianglobal.example",
    "finance": "vikram.singh@meridianglobal.example",
    "it": "suresh.pillai@meridianglobal.example",
    "executive": "cto.executive@meridianglobal.example",
}


def _login(url: str, email: str) -> str | None:
    try:
        r = requests.post(
            f"{url}/auth/token",
            data={"username": email, "password": DEMO_PASSWORD},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        return r.json()["access_token"]
    except requests.RequestException as e:
        print(f"Login failed for {email}: {e}")
        return None


def _query(url: str, token: str, query: str, thread_id: str) -> dict:
    try:
        r = requests.post(
            f"{url}/query",
            json={"query": query, "thread_id": thread_id},
            headers={"Authorization": f"Bearer {token}"},
            timeout=90,
        )
        if r.status_code != 200:
            return {"status": "http_error", "response": f"HTTP {r.status_code}"}
        return r.json()
    except requests.RequestException as e:
        return {"status": "network_error", "response": str(e)}


def _run_golden(url: str) -> dict:
    """Return metrics dict for the golden QA dataset."""
    path = DATA_DIR / "golden_qa.jsonl"
    if not path.exists():
        return {"error": "golden_qa.jsonl missing"}

    entries = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    # Login once per unique role
    tokens = {}
    for e in entries:
        role = e["user_role"]
        if role not in tokens:
            email = EMAIL_BY_ROLE.get(role)
            if email:
                tokens[role] = _login(url, email)

    results = []
    for i, entry in enumerate(entries):
        role = entry["user_role"]
        token = tokens.get(role)
        if not token:
            results.append({**entry, "result": "no_token"})
            continue

        thread_id = f"eval-golden-{i}"
        t0 = time.time()
        resp = _query(url, token, entry["query"], thread_id)
        latency = time.time() - t0

        response_text = (resp.get("response") or "").lower()
        citations = resp.get("citations", [])
        cited_ids = {c.get("doc_id") for c in citations}
        retrieved_doc_ids = set(resp.get("retrieved_docs", [])) or cited_ids
        status = resp.get("status", "")

        expected_ids = set(entry.get("expected_doc_ids", []))
        expected_phrases = entry.get("expected_answer_contains", [])

        # Rule A — expected citations present (subset, not exact):
        if expected_ids:
            answer_hit = set(expected_ids).issubset(set(cited_ids))
            retrieval_hit = set(expected_ids).issubset(set(retrieved_doc_ids or cited_ids))
        else:
            # No expected docs means this is an unauthorized query.
            # Success = query was correctly refused/blocked.
            answer_hit = (status in ("blocked", "refused"))
            retrieval_hit = True

        results.append({
            "query": entry["query"],
            "role": role,
            "status": status,
            "latency": latency,
            "retrieval_hit": retrieval_hit,
            "answer_hit": answer_hit,
            "expected_ids": list(expected_ids),
            "cited_ids": list(cited_ids),
        })

    # Compute aggregate metrics
    scored_retrieval = [r for r in results if r["retrieval_hit"] is not None]
    scored_answer = [r for r in results if r["answer_hit"] is not None]
    latencies = [r["latency"] for r in results if r.get("latency")]

    def pct(lst, p):
        if not lst: return 0.0
        idx = max(0, min(len(lst) - 1, int(len(lst) * p)))
        return round(sorted(lst)[idx], 3)

    retrieval_hits = sum(1 for r in scored_retrieval if r["retrieval_hit"])
    answer_hits = sum(1 for r in scored_answer if r["answer_hit"])
    retrieval_total = len(scored_retrieval)
    answer_total = len(scored_answer)

    retrieval_precision = (
        retrieval_hits / retrieval_total
        if retrieval_total else 0.0
    )
    answer_correctness = (
        answer_hits / answer_total
        if answer_total else 0.0
    )

    return {
        "total": len(results),
        "retrieval_precision": round(retrieval_precision, 3),
        "answer_correctness": round(answer_correctness, 3),
        "retrieval_hits": retrieval_hits,
        "retrieval_total": retrieval_total,
        "answer_hits": answer_hits,
        "answer_total": answer_total,
        "p50_latency": pct(latencies, 0.5),
        "p95_latency": pct(latencies, 0.95),
        "per_entry": results,
    }


def _run_redteam(url: str) -> dict:
    path = DATA_DIR / "redteam.jsonl"
    if not path.exists():
        return {"error": "redteam.jsonl missing"}

    entries = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    token = _login(url, EMAIL_BY_ROLE["employee"])
    if not token:
        return {"error": "no token"}

    blocked_count = 0
    category_stats: dict = {}

    for i, entry in enumerate(entries):
        resp = _query(url, token, entry["prompt"], f"eval-rt-{i}")
        status = resp.get("status", "")
        is_blocked = status in ("blocked",)

        if is_blocked:
            blocked_count += 1

        cat = entry["category"]
        category_stats.setdefault(cat, {"total": 0, "blocked": 0})
        category_stats[cat]["total"] += 1
        if is_blocked:
            category_stats[cat]["blocked"] += 1

    return {
        "total": len(entries),
        "blocked": blocked_count,
        "block_rate": round(blocked_count / len(entries), 3) if entries else 0.0,
        "by_category": category_stats,
    }


def _run_unauthorized(url: str) -> dict:
    path = DATA_DIR / "unauthorized.jsonl"
    if not path.exists():
        return {"error": "unauthorized.jsonl missing"}

    entries = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    tokens = {}
    for e in entries:
        role = e["user_role"]
        if role not in tokens:
            tokens[role] = _login(url, EMAIL_BY_ROLE.get(role, ""))

    refused = 0
    leaked = []

    for i, entry in enumerate(entries):
        token = tokens.get(entry["user_role"])
        if not token:
            continue
        resp = _query(url, token, entry["query"], f"eval-ua-{i}")
        response_text = (resp.get("response") or "").lower()
        citations = resp.get("citations", [])
        cited_ids = {c.get("doc_id") for c in citations}

        forbidden = set(entry.get("forbidden_doc_ids", []))
        if forbidden & cited_ids:
            leaked.append({"query": entry["query"], "leaked": list(forbidden & cited_ids)})
        else:
            refused += 1

    return {
        "total": len(entries),
        "refused": refused,
        "refusal_rate": round(refused / len(entries), 3) if entries else 0.0,
        "leaks": leaked,
    }


def _print_summary(golden, redteam, unauthorized):
    total = golden.get("total", 0)
    ret_prec = golden.get("retrieval_precision", 0) * 100
    ans_corr = golden.get("answer_correctness", 0) * 100
    ret_hits = golden.get("retrieval_hits", sum(1 for r in golden.get("per_entry", []) if r.get("retrieval_hit")))
    ret_total = golden.get("retrieval_total", len(golden.get("per_entry", [])) or total)
    ans_hits = golden.get("answer_hits", sum(1 for r in golden.get("per_entry", []) if r.get("answer_hit")))
    ans_total = golden.get("answer_total", len(golden.get("per_entry", [])) or total)

    print("\n=== EVALUATION SUMMARY ===\n")
    print("GOLDEN QA")
    print(f"  Total entries:          {total}")
    print(f"  Retrieval precision:    {ret_prec:.1f}%  ({ret_hits}/{ret_total} with subset match)")
    print(f"  Answer correctness:     {ans_corr:.1f}%  ({ans_hits}/{ans_total} with subset match + correct block status)")
    print(f"  p50 latency:            {golden.get('p50_latency', 0)}s")
    print(f"  p95 latency:            {golden.get('p95_latency', 0)}s")

    print("\nRED TEAM")
    print(f"  Total prompts:          {redteam.get('total', 0)}")
    print(f"  Blocked:                {redteam.get('blocked', 0)}")
    print(f"  Block rate:             {redteam.get('block_rate', 0) * 100:.1f}%")
    for cat, stats in redteam.get("by_category", {}).items():
        pct = stats["blocked"] / stats["total"] * 100 if stats["total"] else 0
        print(f"    {cat}: {stats['blocked']}/{stats['total']} ({pct:.0f}%)")

    print("\nUNAUTHORIZED")
    print(f"  Total queries:          {unauthorized.get('total', 0)}")
    print(f"  Refused:                {unauthorized.get('refused', 0)}")
    print(f"  Refusal rate:           {unauthorized.get('refusal_rate', 0) * 100:.1f}%")
    if unauthorized.get("leaks"):
        print(f"  LEAKS DETECTED:         {len(unauthorized['leaks'])}")
        for leak in unauthorized["leaks"]:
            print(f"    {leak}")

    print("\n===========================\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000", help="Backend URL")
    args = parser.parse_args()

    print(f"Running evaluation against {args.url}")

    golden = _run_golden(args.url)
    redteam = _run_redteam(args.url)
    unauthorized = _run_unauthorized(args.url)

    _print_summary(golden, redteam, unauthorized)

    report = {
        "url": args.url,
        "golden": golden,
        "redteam": redteam,
        "unauthorized": unauthorized,
    }
    out_path = DATA_DIR / "report.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(f"Report written to {out_path}")


if __name__ == "__main__":
    main()

