from __future__ import annotations

import time
import uuid
from typing import Optional

from app.clients.vllm_client import VLLMClient
from app.metrics.collector import RequestMetrics
from app.metrics.writer import MetricsWriter
from app.router.policy_router import PolicyRouter
from app.schemas import GenerateRequest, GenerateResponse, ResponseMetrics


class GenerateService:
    def __init__(self, *, policy_router: PolicyRouter, vllm_client: VLLMClient, metrics_writer: MetricsWriter):
        self.policy_router = policy_router
        self.vllm_client = vllm_client
        self.metrics_writer = metrics_writer

    async def generate(self, payload: GenerateRequest, mode_override: Optional[str] = None) -> GenerateResponse:
        request_id = str(uuid.uuid4())
        started = time.perf_counter()

        policy = self.policy_router.resolve(payload.stage, mode=mode_override)
        llm_result = await self.vllm_client.generate(prompt=payload.prompt, generation=policy.generation)

        total_latency_ms = (time.perf_counter() - started) * 1000
        metrics = RequestMetrics.build(
            request_id=request_id,
            stage=payload.stage,
            policy_used=policy.name,
            router_mode=policy.mode,
            total_latency_ms=total_latency_ms,
            ttft_ms=llm_result.ttft_ms,
            output_tokens=llm_result.output_tokens,
            prompt_chars=len(payload.prompt or ""),
            metadata=payload.metadata,
        )
        self.metrics_writer.write(metrics.to_dict())

        return GenerateResponse(
            request_id=request_id,
            stage=payload.stage,
            policy={"mode": policy.mode, "name": policy.name, "generation": policy.generation},
            text=llm_result.text,
            model=llm_result.model,
            usage=llm_result.usage,
            metrics=ResponseMetrics(
                total_latency_ms=metrics.total_latency_ms,
                ttft_ms=metrics.ttft_ms,
                output_tokens=metrics.output_tokens,
                policy_used=policy.name,
            ),
        )
