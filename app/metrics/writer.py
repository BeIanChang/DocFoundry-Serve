from __future__ import annotations

import csv
import json
from pathlib import Path
from threading import Lock
from typing import Any, Dict


class MetricsWriter:
    def __init__(self, path: Path, fmt: str = "jsonl"):
        self.path = Path(path)
        self.format = (fmt or "jsonl").strip().lower()
        if self.format not in {"jsonl", "csv"}:
            raise ValueError("METRICS_FORMAT must be either 'jsonl' or 'csv'")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
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

    def write(self, record: Dict[str, Any]) -> None:
        with self._lock:
            if self.format == "jsonl":
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=True) + "\n")
                return

            row = dict(record)
            row["metadata"] = json.dumps(row.get("metadata") or {}, ensure_ascii=True)
            with self.path.open("a", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self._csv_fields)
                writer.writerow({k: row.get(k) for k in self._csv_fields})
