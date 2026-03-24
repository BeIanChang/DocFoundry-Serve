from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import statistics
import time
from typing import Any, Dict, List

import httpx
import yaml


STAGES = ["planning", "synthesis", "refinement"]


def load_yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("benchmark config must be a YAML object")
    return data


def _split_prompt_sections(raw: str) -> List[str]:
    chunks = [part.strip() for part in raw.split("\n---\n")]
    prompts = [chunk for chunk in chunks if chunk]
    return prompts or [raw.strip()]


def load_prompts(prompt_files: Dict[str, Any], root: Path) -> Dict[str, List[str]]:
    prompts: Dict[str, List[str]] = {}
    for stage in STAGES:
        rel = prompt_files.get(stage)
        if not rel:
            raise ValueError(f"missing prompt file for stage: {stage}")
        rel_paths = rel if isinstance(rel, list) else [rel]
        stage_prompts: List[str] = []
        for rel_path in rel_paths:
            p = (root / str(rel_path)).resolve()
            stage_prompts.extend(_split_prompt_sections(p.read_text(encoding="utf-8").strip()))
        prompts[stage] = [prompt for prompt in stage_prompts if prompt]
        if not prompts[stage]:
            raise ValueError(f"no prompts loaded for stage: {stage}")
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
    prompts: Dict[str, List[str]],
    distribution: Dict[str, float],
    metadata_base: Dict[str, Any],
    total_requests: int,
    concurrency: int,
    timeout_seconds: float,
    seed: int,
    auth_token: str | None,
) -> List[Dict[str, Any]]:
    sem = asyncio.Semaphore(max(1, concurrency))
    rng = random.Random(seed)
    timeout = httpx.Timeout(timeout_seconds)

    records: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=timeout) as client:
        async def worker(request_index: int) -> None:
            async with sem:
                stage = choose_stage(rng, distribution)
                stage_prompts = prompts[stage]
                prompt_index = rng.randrange(len(stage_prompts))
                prompt = stage_prompts[prompt_index]
                payload = {
                    "stage": stage,
                    "prompt": prompt,
                    "metadata": {
                        **metadata_base,
                        "request_index": request_index,
                        "benchmark_mode": mode,
                        "prompt_index": prompt_index,
                    },
                }
                headers = {"X-Router-Mode": mode}
                if auth_token:
                    headers["Authorization"] = f"Bearer {auth_token}"
                started = time.perf_counter()
                record: Dict[str, Any] = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "mode": mode,
                    "request_index": request_index,
                    "stage": stage,
                    "prompt_index": prompt_index,
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
    auth_token = args.auth_token or os.environ.get("DOCFOUNDRY_SERVE_TOKEN")
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
            auth_token=auth_token,
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
    parser.add_argument("--auth-token", default=None, help="Bearer token for authenticated gateway")
    return parser.parse_args()


if __name__ == "__main__":
    cli_args = parse_args()
    asyncio.run(main_async(cli_args))
