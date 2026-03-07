from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import router
from app.schemas import GenerateResponse, ResponseMetrics


class _FakeGenerateService:
    async def generate(self, payload, mode_override=None):
        return GenerateResponse(
            request_id="test-id",
            stage=payload.stage,
            policy={"mode": mode_override or "stage_aware", "name": "planning_fast", "generation": {"max_tokens": 96}},
            text="ok",
            model="dummy-model",
            usage={"completion_tokens": 2},
            metrics=ResponseMetrics(total_latency_ms=10.0, ttft_ms=2.0, output_tokens=2, policy_used="planning_fast"),
        )


def test_generate_contract_fields():
    app = FastAPI()
    app.state.generate_service = _FakeGenerateService()
    app.include_router(router)

    client = TestClient(app)
    resp = client.post(
        "/generate",
        json={"stage": "planning", "prompt": "hello", "metadata": {"k": "v"}},
        headers={"X-Router-Mode": "baseline"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["stage"] == "planning"
    assert "metrics" in body
    assert body["metrics"]["policy_used"] == "planning_fast"
