from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import statistics
from typing import Any, Dict, Iterable, List


STAGES = ["planning", "synthesis", "refinement"]


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        raise FileNotFoundError(f"result file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    rank = (len(s) - 1) * (p / 100.0)
    low = int(rank)
    high = min(low + 1, len(s) - 1)
    frac = rank - low
    return s[low] * (1.0 - frac) + s[high] * frac


def compute_metrics(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    row_list = [r for r in rows if r.get("ok")]
    latencies = [float(r["server_total_latency_ms"]) for r in row_list if r.get("server_total_latency_ms") is not None]
    ttfts = [float(r["ttft_ms"]) for r in row_list if r.get("ttft_ms") is not None]
    total_tokens = sum(int(r.get("output_tokens") or 0) for r in row_list)
    total_latency_s = sum(latencies) / 1000.0 if latencies else 0.0
    tokens_per_sec = (total_tokens / total_latency_s) if total_latency_s > 0 else 0.0
    return {
        "count": len(row_list),
        "avg_latency_ms": round(statistics.mean(latencies), 3) if latencies else None,
        "p95_latency_ms": round(percentile(latencies, 95), 3) if latencies else None,
        "tokens_per_sec": round(tokens_per_sec, 3),
        "avg_ttft_ms": round(statistics.mean(ttfts), 3) if ttfts else None,
    }


def build_summary(mode: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    summary_rows: List[Dict[str, Any]] = []
    overall = compute_metrics(rows)
    summary_rows.append({"scope": "overall", "mode": mode, **overall})

    for stage in STAGES:
        stage_rows = [r for r in rows if r.get("stage") == stage]
        metrics = compute_metrics(stage_rows)
        summary_rows.append({"scope": f"stage:{stage}", "mode": mode, **metrics})
    return summary_rows


def print_table(rows: List[Dict[str, Any]]) -> None:
    header = f"{'scope':<18} {'mode':<12} {'count':>7} {'avg_ms':>10} {'p95_ms':>10} {'tok/s':>10} {'avg_ttft':>10}"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{str(r.get('scope')):<18} {str(r.get('mode')):<12} "
            f"{int(r.get('count') or 0):>7} "
            f"{str(r.get('avg_latency_ms')):>10} "
            f"{str(r.get('p95_latency_ms')):>10} "
            f"{str(r.get('tokens_per_sec')):>10} "
            f"{str(r.get('avg_ttft_ms')):>10}"
        )


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["scope", "mode", "count", "avg_latency_ms", "p95_latency_ms", "tokens_per_sec", "avg_ttft_ms"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fields})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze baseline vs stage-aware benchmark outputs.")
    parser.add_argument("--baseline", default="data/benchmarks/results_baseline.jsonl")
    parser.add_argument("--stage-aware", default="data/benchmarks/results_stage_aware.jsonl")
    parser.add_argument("--output", default="data/benchmarks/analysis_summary.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    baseline_rows = read_jsonl(Path(args.baseline).resolve())
    stage_rows = read_jsonl(Path(args.stage_aware).resolve())

    summary = build_summary("baseline", baseline_rows) + build_summary("stage_aware", stage_rows)
    print_table(summary)

    out_path = Path(args.output).resolve()
    write_csv(out_path, summary)
    print(f"\nWrote summary CSV: {out_path}")


if __name__ == "__main__":
    main()
