from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.errors import (
    AuthError,
    QueueFullError,
    QueueTimeoutError,
    StageOverloadedError,
    TimeoutBudgetExceededError,
    VLLMRetryExhaustedError,
)
from app.security.auth import decode_docfoundry_jwt, parse_bearer_token
from app.schemas import GenerateRequest, GenerateResponse


router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    payload: GenerateRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_router_mode: Optional[str] = Header(default=None, alias="X-Router-Mode"),
):
    settings = request.app.state.settings
    service = request.app.state.generate_service
    mode_override = x_router_mode.strip().lower() if x_router_mode else None

    auth_context = None
    try:
        if authorization:
            token = parse_bearer_token(authorization)
            auth_context = decode_docfoundry_jwt(token, secret=settings.jwt_secret, algorithm=settings.jwt_algorithm)
        elif settings.auth_required:
            raise AuthError("missing authorization header")
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    try:
        return await service.generate(payload, mode_override=mode_override, auth_context=auth_context)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except QueueFullError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except StageOverloadedError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except QueueTimeoutError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TimeoutBudgetExceededError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except VLLMRetryExhaustedError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request):
    details = await request.app.state.health_service.readiness()
    status_code = 200 if details.get("ready") else 503
    return JSONResponse(status_code=status_code, content=details)
