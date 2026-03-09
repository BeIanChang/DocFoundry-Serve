from __future__ import annotations

import asyncio
import time
import uuid
from typing import Optional

from app.clients.vllm_client import VLLMClient
from app.control.admission import AdmissionController
from app.errors import TimeoutBudgetExceededError
from app.metrics.collector import RequestMetrics
from app.metrics.writer import MetricsWriter
from app.router.policy_router import PolicyRouter
from app.security.auth import AuthContext
from app.schemas import GenerateRequest, GenerateResponse, ResponseMetrics


class GenerateService:
    def __init__(
        self,
        *,
        policy_router: PolicyRouter,
        vllm_client: VLLMClient,
        metrics_writer: MetricsWriter,
        admission: AdmissionController,
        request_timeout_seconds: float,
    ):
        self.policy_router = policy_router
        self.vllm_client = vllm_client
        self.metrics_writer = metrics_writer
        self.admission = admission
        self.request_timeout_seconds = max(0.1, float(request_timeout_seconds))

    async def generate(
        self,
        payload: GenerateRequest,
        *,
        mode_override: Optional[str] = None,
        auth_context: Optional[AuthContext] = None,
    ) -> GenerateResponse:
        request_id = str(uuid.uuid4())
        started = time.perf_counter()

        lease = await self.admission.acquire(payload.stage)
        try:
            policy = self.policy_router.resolve(payload.stage, mode=mode_override)
            try:
                llm_result = await asyncio.wait_for(
                    self.vllm_client.generate(prompt=payload.prompt, generation=policy.generation),
                    timeout=self.request_timeout_seconds,
                )
            except asyncio.TimeoutError as exc:
                raise TimeoutBudgetExceededError("request timeout budget exceeded") from exc

            total_latency_ms = (time.perf_counter() - started) * 1000
            metadata = dict(payload.metadata or {})
            if auth_context is not None:
                metadata.setdefault("auth_user_id", auth_context.user_id)
                if auth_context.email:
                    metadata.setdefault("auth_email", auth_context.email)

            metrics = RequestMetrics.build(
                request_id=request_id,
                stage=payload.stage,
                policy_used=policy.name,
                router_mode=policy.mode,
                total_latency_ms=total_latency_ms,
                ttft_ms=llm_result.ttft_ms,
                output_tokens=llm_result.output_tokens,
                prompt_chars=len(payload.prompt or ""),
                metadata=metadata,
            )
            await self.metrics_writer.write(metrics.to_dict())

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
        finally:
            await lease.release()
