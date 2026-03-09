from __future__ import annotations

from typing import Any, Dict

from app.clients.vllm_client import VLLMClient
from app.control.admission import AdmissionController


class HealthService:
    def __init__(self, *, vllm_client: VLLMClient, admission: AdmissionController):
        self.vllm_client = vllm_client
        self.admission = admission

    async def readiness(self) -> Dict[str, Any]:
        upstream = await self.vllm_client.check_ready()
        admission_snapshot = await self.admission.snapshot()
        ready = bool(upstream.get("upstream_ok") and upstream.get("model_loaded"))
        return {
            "ready": ready,
            "upstream": upstream,
            "admission": {
                "max_in_flight": admission_snapshot.max_in_flight,
                "in_flight": admission_snapshot.in_flight,
                "waiting": admission_snapshot.waiting,
                "max_queue": admission_snapshot.max_queue,
                "stage_in_flight": admission_snapshot.stage_in_flight,
                "stage_waiting": admission_snapshot.stage_waiting,
            },
        }
