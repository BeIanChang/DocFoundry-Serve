from __future__ import annotations

from fastapi import FastAPI

from app.api import router as api_router
from app.clients.vllm_client import VLLMClient
from app.metrics.writer import MetricsWriter
from app.router.policy_router import PolicyRouter
from app.services.generate_service import GenerateService
from app.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()

    app = FastAPI(title="DocFoundry-Serve", version="0.1.0")

    policy_router = PolicyRouter(config_path=cfg.policy_config_path, default_mode=cfg.router_mode)
    vllm_client = VLLMClient(
        base_url=cfg.vllm_base_url,
        model=cfg.vllm_model,
        timeout_seconds=cfg.request_timeout_seconds,
    )
    metrics_writer = MetricsWriter(path=cfg.metrics_path, fmt=cfg.metrics_format)

    app.state.generate_service = GenerateService(
        policy_router=policy_router,
        vllm_client=vllm_client,
        metrics_writer=metrics_writer,
    )

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await vllm_client.close()

    app.include_router(api_router)
    return app


app = create_app()
