from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import router
from app.schemas import GenerateResponse, ResponseMetrics


class _FakeGenerateService:
    async def generate(self, payload, mode_override=None, auth_context=None):
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
    app.state.settings = SimpleNamespace(auth_required=False, jwt_secret="dev-secret-change-me", jwt_algorithm="HS256")
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


def test_generate_requires_docfoundry_compatible_jwt_when_enabled():
    app = FastAPI()
    app.state.generate_service = _FakeGenerateService()
    app.state.settings = SimpleNamespace(auth_required=True, jwt_secret="dev-secret-change-me", jwt_algorithm="HS256")
    app.include_router(router)

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "user-123",
            "email": "user@example.com",
            "name": "Doc Foundry",
            "iat": now,
            "exp": now + timedelta(minutes=30),
        },
        "dev-secret-change-me",
        algorithm="HS256",
    )

    client = TestClient(app)
    resp = client.post(
        "/generate",
        json={"stage": "planning", "prompt": "hello"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    missing = client.post("/generate", json={"stage": "planning", "prompt": "hello"})
    assert missing.status_code == 401
