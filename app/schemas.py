from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


Stage = Literal["planning", "synthesis", "refinement"]


class GenerateRequest(BaseModel):
    stage: Stage
    prompt: str = Field(..., min_length=1)
    metadata: Optional[Dict[str, Any]] = None


class ResponseMetrics(BaseModel):
    total_latency_ms: float
    ttft_ms: Optional[float] = None
    output_tokens: int
    policy_used: str


class GenerateResponse(BaseModel):
    request_id: str
    stage: Stage
    policy: Dict[str, Any]
    text: str
    model: Optional[str] = None
    usage: Dict[str, Any] = Field(default_factory=dict)
    metrics: ResponseMetrics
