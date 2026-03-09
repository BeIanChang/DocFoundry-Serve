from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class MetricsWriter:
    def __init__(
        self,
        path: Path,
        fmt: str = "jsonl",
        *,
        batch_size: int = 50,
        flush_interval_seconds: float = 1.0,
    ):
        self.path = Path(path)
        self.format = (fmt or "jsonl").strip().lower()
        if self.format not in {"jsonl", "csv"}:
            raise ValueError("METRICS_FORMAT must be either 'jsonl' or 'csv'")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.batch_size = max(1, int(batch_size))
        self.flush_interval_seconds = max(0.05, float(flush_interval_seconds))
        self._queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._stopping = False
        self._csv_fields = [
            "timestamp",
            "request_id",
            "stage",
            "policy_used",
            "router_mode",
            "total_latency_ms",
            "ttft_ms",
            "output_tokens",
            "prompt_chars",
            "metadata",
        ]
        if self.format == "csv" and not self.path.exists():
            with self.path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self._csv_fields)
                writer.writeheader()

    async def start(self) -> None:
        if self._worker_task is not None:
            return
        self._stopping = False
        self._worker_task = asyncio.create_task(self._worker(), name="metrics-writer")

    async def stop(self) -> None:
        self._stopping = True
        if self._worker_task is None:
            return
        await self._queue.put({"__flush__": True})
        await self._worker_task
        self._worker_task = None

    async def write(self, record: Dict[str, Any]) -> None:
        await self._queue.put(record)

    async def _worker(self) -> None:
        buffer: List[Dict[str, Any]] = []
        while True:
            timeout = self.flush_interval_seconds if buffer else None
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                if item.get("__flush__"):
                    if buffer:
                        self._flush(buffer)
                        buffer = []
                    if self._stopping and self._queue.empty():
                        return
                    continue

                buffer.append(item)
                if len(buffer) >= self.batch_size:
                    self._flush(buffer)
                    buffer = []
            except asyncio.TimeoutError:
                if buffer:
                    self._flush(buffer)
                    buffer = []
                if self._stopping and self._queue.empty():
                    return

    def _flush(self, records: List[Dict[str, Any]]) -> None:
        if not records:
            return
        if self.format == "jsonl":
            with self.path.open("a", encoding="utf-8") as f:
                for record in records:
                    f.write(json.dumps(record, ensure_ascii=True) + "\n")
            return

        with self.path.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self._csv_fields)
            for record in records:
                row = dict(record)
                row["metadata"] = json.dumps(row.get("metadata") or {}, ensure_ascii=True)
                writer.writerow({k: row.get(k) for k in self._csv_fields})
