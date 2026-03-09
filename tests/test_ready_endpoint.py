from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import router


class _FakeHealthService:
    def __init__(self, ready: bool):
        self.ready = ready

    async def readiness(self):
        return {
            "ready": self.ready,
            "upstream": {"upstream_ok": self.ready, "model_loaded": self.ready},
            "admission": {"in_flight": 0, "waiting": 0},
        }


class _FakeGenerateService:
    async def generate(self, payload, mode_override=None, auth_context=None):
        return {
            "request_id": "x",
            "stage": payload.stage,
            "policy": {"mode": "stage_aware", "name": "planning_fast", "generation": {}},
            "text": "ok",
            "usage": {},
            "metrics": {
                "total_latency_ms": 1.0,
                "ttft_ms": None,
                "output_tokens": 1,
                "policy_used": "planning_fast",
            },
        }


def test_ready_status_codes():
    app = FastAPI()
    app.state.generate_service = _FakeGenerateService()
    app.state.settings = SimpleNamespace(auth_required=False, jwt_secret="dev-secret-change-me", jwt_algorithm="HS256")
    app.state.health_service = _FakeHealthService(ready=True)
    app.include_router(router)

    client = TestClient(app)
    ok = client.get("/ready")
    assert ok.status_code == 200

    app.state.health_service = _FakeHealthService(ready=False)
    not_ready = client.get("/ready")
    assert not_ready.status_code == 503
