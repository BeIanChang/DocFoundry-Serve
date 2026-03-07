from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RequestMetrics:
    request_id: str
    stage: str
    policy_used: str
    router_mode: str
    total_latency_ms: float
    ttft_ms: Optional[float]
    output_tokens: int
    prompt_chars: int
    metadata: Dict[str, Any]
    timestamp: str

    @staticmethod
    def build(
        *,
        request_id: str,
        stage: str,
        policy_used: str,
        router_mode: str,
        total_latency_ms: float,
        ttft_ms: Optional[float],
        output_tokens: int,
        prompt_chars: int,
        metadata: Optional[Dict[str, Any]],
    ) -> "RequestMetrics":
        return RequestMetrics(
            request_id=request_id,
            stage=stage,
            policy_used=policy_used,
            router_mode=router_mode,
            total_latency_ms=round(float(total_latency_ms), 3),
            ttft_ms=round(float(ttft_ms), 3) if ttft_ms is not None else None,
            output_tokens=int(output_tokens),
            prompt_chars=int(prompt_chars),
            metadata=metadata or {},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "request_id": self.request_id,
            "stage": self.stage,
            "policy_used": self.policy_used,
            "router_mode": self.router_mode,
            "total_latency_ms": self.total_latency_ms,
            "ttft_ms": self.ttft_ms,
            "output_tokens": self.output_tokens,
            "prompt_chars": self.prompt_chars,
            "metadata": self.metadata,
        }
