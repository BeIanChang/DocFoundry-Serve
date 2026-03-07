from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    router_mode: str
    policy_config_path: Path
    vllm_base_url: str
    vllm_model: str
    request_timeout_seconds: float
    metrics_path: Path
    metrics_format: str


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    root = _project_root()
    return Settings(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        router_mode=os.environ.get("ROUTER_MODE", "stage_aware").strip().lower(),
        policy_config_path=Path(os.environ.get("POLICY_CONFIG_PATH", str(root / "config" / "policies.yaml"))),
        vllm_base_url=os.environ.get("VLLM_BASE_URL", "http://localhost:8001/v1").rstrip("/"),
        vllm_model=os.environ.get("VLLM_MODEL", "Qwen/Qwen2.5-3B-Instruct"),
        request_timeout_seconds=float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "120")),
        metrics_path=Path(os.environ.get("METRICS_PATH", str(root / "data" / "metrics" / "gateway_metrics.jsonl"))),
        metrics_format=os.environ.get("METRICS_FORMAT", "jsonl").strip().lower(),
    )
