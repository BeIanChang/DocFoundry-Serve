from __future__ import annotations

from fastapi import FastAPI

from app.api import router as api_router
from app.clients.vllm_client import VLLMClient
from app.control.admission import AdmissionController
from app.metrics.writer import MetricsWriter
from app.router.policy_router import PolicyRouter
from app.services.generate_service import GenerateService
from app.services.health_service import HealthService
from app.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()

    app = FastAPI(title="DocFoundry-Serve", version="0.1.0")

    policy_router = PolicyRouter(config_path=cfg.policy_config_path, default_mode=cfg.router_mode)
    vllm_client = VLLMClient(
        base_url=cfg.vllm_base_url,
        model=cfg.vllm_model,
        timeout_seconds=cfg.request_timeout_seconds,
        max_retries=cfg.vllm_max_retries,
        retry_backoff_ms=cfg.vllm_retry_backoff_ms,
    )
    metrics_writer = MetricsWriter(
        path=cfg.metrics_path,
        fmt=cfg.metrics_format,
        batch_size=cfg.metrics_batch_size,
        flush_interval_seconds=cfg.metrics_flush_interval_seconds,
    )
    admission = AdmissionController(
        max_in_flight=cfg.max_in_flight,
        max_queue=cfg.max_queue,
        queue_wait_timeout_seconds=cfg.queue_wait_timeout_seconds,
        stage_queue_limits=cfg.stage_queue_limits,
        stage_in_flight_limits=cfg.stage_in_flight_limits,
    )

    app.state.generate_service = GenerateService(
        policy_router=policy_router,
        vllm_client=vllm_client,
        metrics_writer=metrics_writer,
        admission=admission,
        request_timeout_seconds=cfg.request_timeout_seconds,
    )
    app.state.health_service = HealthService(vllm_client=vllm_client, admission=admission)
    app.state.settings = cfg

    @app.on_event("startup")
    async def _startup() -> None:
        await metrics_writer.start()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await metrics_writer.stop()
        await vllm_client.close()

    app.include_router(api_router)
    return app


app = create_app()
