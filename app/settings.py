from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os
from typing import Dict


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_stage_limits(raw: str | None, fallback: Dict[str, int]) -> Dict[str, int]:
    if not raw:
        return dict(fallback)
    out: Dict[str, int] = dict(fallback)
    for piece in raw.split(","):
        if not piece.strip() or ":" not in piece:
            continue
        key, value = piece.split(":", 1)
        try:
            out[key.strip().lower()] = max(0, int(value.strip()))
        except ValueError:
            continue
    return out


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    router_mode: str
    policy_config_path: Path
    vllm_base_url: str
    vllm_model: str
    request_timeout_seconds: float
    vllm_max_retries: int
    vllm_retry_backoff_ms: int
    metrics_path: Path
    metrics_format: str
    metrics_batch_size: int
    metrics_flush_interval_seconds: float
    auth_required: bool
    jwt_secret: str
    jwt_algorithm: str
    max_in_flight: int
    max_queue: int
    queue_wait_timeout_seconds: float
    stage_queue_limits: Dict[str, int]
    stage_in_flight_limits: Dict[str, int]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    root = _project_root()
    default_stage_queue_limits = {"planning": 200, "synthesis": 120, "refinement": 120}
    default_stage_in_flight_limits = {"planning": 48, "synthesis": 24, "refinement": 24}
    return Settings(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        router_mode=os.environ.get("ROUTER_MODE", "stage_aware").strip().lower(),
        policy_config_path=Path(os.environ.get("POLICY_CONFIG_PATH", str(root / "config" / "policies.yaml"))),
        vllm_base_url=os.environ.get("VLLM_BASE_URL", "http://localhost:8001/v1").rstrip("/"),
        vllm_model=os.environ.get("VLLM_MODEL", "Qwen/Qwen2.5-3B-Instruct"),
        request_timeout_seconds=float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "120")),
        vllm_max_retries=max(0, int(os.environ.get("VLLM_MAX_RETRIES", "2"))),
        vllm_retry_backoff_ms=max(1, int(os.environ.get("VLLM_RETRY_BACKOFF_MS", "250"))),
        metrics_path=Path(os.environ.get("METRICS_PATH", str(root / "data" / "metrics" / "gateway_metrics.jsonl"))),
        metrics_format=os.environ.get("METRICS_FORMAT", "jsonl").strip().lower(),
        metrics_batch_size=max(1, int(os.environ.get("METRICS_BATCH_SIZE", "50"))),
        metrics_flush_interval_seconds=max(0.05, float(os.environ.get("METRICS_FLUSH_INTERVAL_SECONDS", "1.0"))),
        auth_required=_as_bool(os.environ.get("AUTH_REQUIRED"), default=False),
        jwt_secret=os.environ.get("JWT_SECRET", "dev-secret-change-me"),
        jwt_algorithm=os.environ.get("JWT_ALGORITHM", "HS256"),
        max_in_flight=max(1, int(os.environ.get("MAX_IN_FLIGHT", "64"))),
        max_queue=max(0, int(os.environ.get("MAX_QUEUE", "512"))),
        queue_wait_timeout_seconds=max(0.01, float(os.environ.get("QUEUE_WAIT_TIMEOUT_SECONDS", "2.0"))),
        stage_queue_limits=_parse_stage_limits(os.environ.get("STAGE_QUEUE_LIMITS"), default_stage_queue_limits),
        stage_in_flight_limits=_parse_stage_limits(
            os.environ.get("STAGE_IN_FLIGHT_LIMITS"),
            default_stage_in_flight_limits,
        ),
    )
