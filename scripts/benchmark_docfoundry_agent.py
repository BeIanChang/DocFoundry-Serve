from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List

import httpx


QUESTION_BANK = {
    "hr_pto_one_user": [
        "Can unused vacation days carry over into the next calendar year?",
        "How many unused PTO days can a manager approve for carryover without HR?",
        "When is HR approval required for PTO carryover?",
        "What happens if someone submits a carryover request after December 31?",
        "What documentation has to be included in an approved PTO carryover exception?",
    ],
    "incidents_one_user": [
        "What caused the April API latency incident and what was the first mitigation step?",
        "When should the database owner be escalated during an API latency event?",
        "What latency threshold turns this into an incident, and what checks should happen first?",
        "How long did the incident last and when did rollback happen?",
        "Which endpoints were most affected and what was the measured impact?",
    ],
    "contracts_one_user": [
        "How long is the contract term and when would it renew if nobody gives notice?",
        "What are the payment terms and late-fee rule?",
        "How fast does the vendor need to notify us after a confirmed security incident?",
        "Which document controls if the security timeline conflicts with the MSA?",
        "What dates define the current subscription term on the order form?",
    ],
}


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok_rows = [r for r in rows if r.get("ok")]
    latencies = [float(r["latency_ms"]) for r in ok_rows]
    started_at = [float(r["started_at_s"]) for r in rows if r.get("started_at_s") is not None]
    ended_at = [float(r["ended_at_s"]) for r in rows if r.get("ended_at_s") is not None]
    def percentile(values: List[float], pct: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        index = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
        return ordered[index]
    wall_time_s = (max(ended_at) - min(started_at)) if started_at and ended_at else None
    return {
        "total_queries": len(rows),
        "success": len(ok_rows),
        "error": len(rows) - len(ok_rows),
        "avg_latency_ms": round(statistics.mean(latencies), 3) if latencies else None,
        "p95_latency_ms": round(percentile(latencies, 95) or 0.0, 3) if latencies else None,
        "p99_latency_ms": round(percentile(latencies, 99) or 0.0, 3) if latencies else None,
        "wall_time_s": round(wall_time_s, 3) if wall_time_s is not None else None,
        "requests_per_sec": round(len(rows) / wall_time_s, 3) if wall_time_s else None,
        "wrong_tenant_leakage_rate": round(sum(1 for r in ok_rows if r.get("wrong_tenant_leak")) / len(ok_rows), 4) if ok_rows else None,
        "citation_presence_rate": round(sum(1 for r in ok_rows if r.get("citation_count", 0) > 0) / len(ok_rows), 4) if ok_rows else None,
    }


def build_work_items(tenants: List[Dict[str, Any]], queries_per_tenant: int, seed: int, loop_engine: str) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    items: List[Dict[str, Any]] = []
    for tenant in tenants:
        topic = tenant["topic"]
        questions = QUESTION_BANK.get(topic) or []
        if not questions:
            continue
        for i in range(queries_per_tenant):
            question = questions[i % len(questions)] if i < len(questions) else rng.choice(questions)
            items.append(
                {
                    "tenant_id": tenant["tenant_id"],
                    "topic": topic,
                    "allowed_doc_ids": set(tenant.get("document_ids") or []),
                    "headers": {"Authorization": f"Bearer {tenant['token']}"},
                    "request": {
                        "message": question,
                        "kb_id": tenant["kb"]["id"],
                        "top_k": 5,
                        "max_steps": 12,
                        "mode": "auto",
                        "loop_engine": loop_engine,
                        "return_steps": True,
                    },
                    "question": question,
                }
            )
    return items


async def run_benchmark(base_url: str, items: List[Dict[str, Any]], concurrency: int, timeout_seconds: float) -> List[Dict[str, Any]]:
    sem = asyncio.Semaphore(max(1, concurrency))
    rows: List[Dict[str, Any]] = []
    timeout = httpx.Timeout(timeout_seconds)

    async with httpx.AsyncClient(timeout=timeout) as client:
        async def worker(item: Dict[str, Any]) -> None:
            async with sem:
                started = time.perf_counter()
                row: Dict[str, Any] = {
                    "tenant_id": item["tenant_id"],
                    "topic": item["topic"],
                    "question": item["question"],
                    "ok": False,
                    "latency_ms": None,
                    "error": None,
                    "citation_count": 0,
                    "wrong_tenant_leak": False,
                    "started_at_s": started,
                    "ended_at_s": None,
                }
                try:
                    resp = await client.post(f"{base_url}/agent/query", json=item["request"], headers=item["headers"])
                    ended = time.perf_counter()
                    row["latency_ms"] = round((ended - started) * 1000, 3)
                    row["ended_at_s"] = ended
                    resp.raise_for_status()
                    body = resp.json()
                    citations = body.get("citations") or []
                    cited_doc_ids = {
                        c.get("metadata", {}).get("document_id")
                        for c in citations
                        if isinstance(c, dict) and isinstance(c.get("metadata"), dict) and c.get("metadata", {}).get("document_id")
                    }
                    row["ok"] = True
                    row["citation_count"] = len(citations)
                    row["wrong_tenant_leak"] = any(doc_id not in item["allowed_doc_ids"] for doc_id in cited_doc_ids)
                    row["run_id"] = body.get("run_id")
                except Exception as exc:
                    ended = time.perf_counter()
                    row["latency_ms"] = round((ended - started) * 1000, 3)
                    row["ended_at_s"] = ended
                    row["error"] = str(exc)
                rows.append(row)

        await asyncio.gather(*(worker(item) for item in items))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark DocFoundry /agent/query across loaded tenants.")
    parser.add_argument("--base-url", default="http://127.0.0.1:28000")
    parser.add_argument("--load-results", default="data/generated/multi_tenant_corpus/load_results.json")
    parser.add_argument("--output", default="data/generated/multi_tenant_corpus/agent_benchmark_results.jsonl")
    parser.add_argument("--queries-per-tenant", type=int, default=5)
    parser.add_argument("--loop-engine", default="classic", choices=["classic", "langgraph"])
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    load_results_path = (root / args.load_results).resolve()
    output_path = (root / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.loads(load_results_path.read_text(encoding="utf-8"))
    tenants = payload.get("tenants", [])
    items = build_work_items(tenants, args.queries_per_tenant, args.seed, args.loop_engine)
    rows = asyncio.run(run_benchmark(args.base_url, items, args.concurrency, args.timeout_seconds))

    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")

    print(json.dumps(summarize(rows), ensure_ascii=True))
    print(f"Wrote results -> {output_path}")


if __name__ == "__main__":
    main()
