from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import statistics
import time
from typing import Any, Dict, List, Tuple

import httpx
import yaml


STAGES = ["planning", "synthesis", "refinement"]


def load_yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("benchmark config must be a YAML object")
    return data


def load_prompts(prompt_files: Dict[str, str], root: Path) -> Dict[str, str]:
    prompts: Dict[str, str] = {}
    for stage in STAGES:
        rel = prompt_files.get(stage)
        if not rel:
            raise ValueError(f"missing prompt file for stage: {stage}")
        p = (root / rel).resolve()
        prompts[stage] = p.read_text(encoding="utf-8").strip()
    return prompts


def choose_stage(rng: random.Random, distribution: Dict[str, float]) -> str:
    weights: List[float] = [float(distribution.get(stage, 0.0)) for stage in STAGES]
    total = sum(weights)
    if total <= 0:
        raise ValueError("stage_distribution weights must sum to > 0")
    normalized = [w / total for w in weights]
    return rng.choices(STAGES, weights=normalized, k=1)[0]


async def run_mode(
    *,
    mode: str,
    url: str,
    prompts: Dict[str, str],
    distribution: Dict[str, float],
    metadata_base: Dict[str, Any],
    total_requests: int,
    concurrency: int,
    timeout_seconds: float,
    seed: int,
) -> List[Dict[str, Any]]:
    sem = asyncio.Semaphore(max(1, concurrency))
    rng = random.Random(seed)
    timeout = httpx.Timeout(timeout_seconds)

    records: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=timeout) as client:
        async def worker(request_index: int) -> None:
            async with sem:
                stage = choose_stage(rng, distribution)
                prompt = prompts[stage]
                payload = {
                    "stage": stage,
                    "prompt": prompt,
                    "metadata": {
                        **metadata_base,
                        "request_index": request_index,
                        "benchmark_mode": mode,
                    },
                }
                headers = {"X-Router-Mode": mode}
                started = time.perf_counter()
                record: Dict[str, Any] = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "mode": mode,
                    "request_index": request_index,
                    "stage": stage,
                    "ok": False,
                    "status_code": None,
                    "error": None,
                    "client_latency_ms": None,
                    "server_total_latency_ms": None,
                    "ttft_ms": None,
                    "output_tokens": 0,
                    "policy_used": None,
                }
                try:
                    resp = await client.post(url, json=payload, headers=headers)
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    record["client_latency_ms"] = round(elapsed_ms, 3)
                    record["status_code"] = resp.status_code

                    if resp.status_code != 200:
                        record["error"] = resp.text
                        records.append(record)
                        return

                    body = resp.json()
                    metrics = body.get("metrics") or {}
                    record["ok"] = True
                    record["server_total_latency_ms"] = metrics.get("total_latency_ms")
                    record["ttft_ms"] = metrics.get("ttft_ms")
                    record["output_tokens"] = int(metrics.get("output_tokens") or 0)
                    record["policy_used"] = metrics.get("policy_used")
                    records.append(record)
                except Exception as exc:
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    record["client_latency_ms"] = round(elapsed_ms, 3)
                    record["error"] = str(exc)
                    records.append(record)

        await asyncio.gather(*(worker(i) for i in range(total_requests)))
    return records


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok_rows = [r for r in rows if r.get("ok")]
    latencies = [float(r["server_total_latency_ms"]) for r in ok_rows if r.get("server_total_latency_ms") is not None]
    total_tokens = sum(int(r.get("output_tokens") or 0) for r in ok_rows)
    total_latency_s = sum(latencies) / 1000 if latencies else 0.0
    tps = (total_tokens / total_latency_s) if total_latency_s > 0 else 0.0
    return {
        "total_requests": len(rows),
        "success": len(ok_rows),
        "error": len(rows) - len(ok_rows),
        "avg_latency_ms": round(statistics.mean(latencies), 3) if latencies else None,
        "tokens_per_sec": round(tps, 3),
    }


async def main_async(args: argparse.Namespace) -> None:
    config_path = Path(args.config).resolve()
    root = config_path.parents[1]
    cfg = load_yaml(config_path)

    url = str(cfg.get("gateway_url") or "http://localhost:8000/generate")
    total_requests = int(cfg.get("total_requests") or 120)
    concurrency = int(cfg.get("concurrency") or 12)
    timeout_seconds = float(cfg.get("timeout_seconds") or 90)
    distribution = cfg.get("stage_distribution") or {}
    metadata_base = cfg.get("metadata_base") or {}
    prompt_files = cfg.get("prompt_files") or {}

    prompts = load_prompts(prompt_files, root)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for offset, mode in enumerate(args.modes):
        mode_seed = args.seed + (offset * 997)
        rows = await run_mode(
            mode=mode,
            url=url,
            prompts=prompts,
            distribution=distribution,
            metadata_base=metadata_base,
            total_requests=total_requests,
            concurrency=concurrency,
            timeout_seconds=timeout_seconds,
            seed=mode_seed,
        )
        out_path = output_dir / f"results_{mode}.jsonl"
        write_jsonl(out_path, rows)
        print(f"[{mode}] wrote {len(rows)} rows -> {out_path}")
        print(f"[{mode}] summary: {json.dumps(summarize(rows), ensure_ascii=True)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run mixed-stage benchmark against /generate.")
    parser.add_argument("--config", default="config/benchmark.yaml", help="Path to benchmark YAML config")
    parser.add_argument(
        "--modes",
        nargs="+",
        default=["baseline", "stage_aware"],
        choices=["baseline", "stage_aware"],
        help="Router modes to benchmark",
    )
    parser.add_argument("--output-dir", default="data/benchmarks", help="Directory for benchmark JSONL files")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args()


if __name__ == "__main__":
    cli_args = parse_args()
    asyncio.run(main_async(cli_args))
