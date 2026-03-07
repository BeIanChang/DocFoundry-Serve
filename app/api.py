from __future__ import annotations

from typing import Optional

import httpx
from fastapi import APIRouter, Header, HTTPException, Request

from app.schemas import GenerateRequest, GenerateResponse


router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    payload: GenerateRequest,
    request: Request,
    x_router_mode: Optional[str] = Header(default=None, alias="X-Router-Mode"),
):
    service = request.app.state.generate_service
    mode_override = x_router_mode.strip().lower() if x_router_mode else None
    try:
        return await service.generate(payload, mode_override=mode_override)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        body = exc.response.text if exc.response is not None else str(exc)
        raise HTTPException(status_code=502, detail=f"vLLM request failed: {body}") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"vLLM connection failed: {exc}") from exc


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}
