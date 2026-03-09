from __future__ import annotations

from dataclasses import dataclass
import asyncio
import json
import math
import time
from typing import Any, Dict, Optional

import httpx

from app.errors import VLLMClientError, VLLMRetryExhaustedError


@dataclass(frozen=True)
class VLLMResult:
    text: str
    output_tokens: int
    ttft_ms: Optional[float]
    usage: Dict[str, Any]
    model: Optional[str]


def _estimate_output_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, int(math.ceil(len(text) / 4)))


def _extract_delta_content(choice: Dict[str, Any]) -> str:
    delta = choice.get("delta") or {}
    content = delta.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


class VLLMClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
        max_retries: int = 2,
        retry_backoff_ms: int = 250,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout_seconds)
        self.max_retries = max(0, int(max_retries))
        self.retry_backoff_ms = max(1, int(retry_backoff_ms))
        self.retryable_status_codes = {408, 409, 425, 429, 500, 502, 503, 504}

    async def close(self) -> None:
        await self.client.aclose()

    async def generate(self, *, prompt: str, generation: Dict[str, Any]) -> VLLMResult:
        attempts = self.max_retries + 1
        last_error: Optional[VLLMClientError] = None
        for attempt in range(1, attempts + 1):
            try:
                return await self._generate_once(prompt=prompt, generation=generation)
            except VLLMClientError as exc:
                last_error = exc
                should_retry = exc.retryable and attempt < attempts
                if not should_retry:
                    raise VLLMRetryExhaustedError(
                        message=f"vLLM request failed after {attempt} attempt(s): {exc}",
                        retryable=False,
                        status_code=exc.status_code,
                        response_body=exc.response_body,
                    ) from exc

                backoff_seconds = (self.retry_backoff_ms * attempt) / 1000.0
                await asyncio.sleep(backoff_seconds)

        raise VLLMRetryExhaustedError(
            message="vLLM request failed without specific upstream error",
            retryable=False,
            response_body=str(last_error) if last_error else None,
        )

    async def _generate_once(self, *, prompt: str, generation: Dict[str, Any]) -> VLLMResult:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        payload.update(generation or {})

        start = time.perf_counter()
        ttft_ms: Optional[float] = None
        usage: Dict[str, Any] = {}
        output_parts: list[str] = []

        try:
            async with self.client.stream("POST", "/chat/completions", json=payload) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    text = body.decode("utf-8", errors="ignore") if body else ""
                    raise VLLMClientError(
                        message="vLLM upstream returned error",
                        retryable=resp.status_code in self.retryable_status_codes,
                        status_code=resp.status_code,
                        response_body=text,
                    )

                async for line in resp.aiter_lines():
                    clean = (line or "").strip()
                    if not clean or not clean.startswith("data:"):
                        continue
                    data = clean[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices") or []
                    if choices and isinstance(choices[0], dict):
                        piece = _extract_delta_content(choices[0])
                        if piece:
                            if ttft_ms is None:
                                ttft_ms = (time.perf_counter() - start) * 1000
                            output_parts.append(piece)
                    if chunk.get("usage"):
                        usage = chunk["usage"]

            output_text = "".join(output_parts)
            if not output_text:
                return await self._generate_non_stream(prompt=prompt, generation=generation)

            output_tokens = int(
                usage.get("completion_tokens")
                or usage.get("output_tokens")
                or _estimate_output_tokens(output_text)
            )
            return VLLMResult(
                text=output_text,
                output_tokens=output_tokens,
                ttft_ms=ttft_ms,
                usage=usage,
                model=self.model,
            )
        except httpx.TimeoutException as exc:
            raise VLLMClientError(message="vLLM request timed out", retryable=True) from exc
        except httpx.RequestError as exc:
            raise VLLMClientError(message=f"vLLM request error: {exc}", retryable=True) from exc
        except VLLMClientError:
            raise
        except Exception as exc:
            raise VLLMClientError(message=f"unexpected vLLM error: {exc}", retryable=False) from exc

    async def _generate_non_stream(self, *, prompt: str, generation: Dict[str, Any]) -> VLLMResult:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        payload.update(generation or {})
        try:
            resp = await self.client.post("/chat/completions", json=payload)
            if resp.status_code >= 400:
                raise VLLMClientError(
                    message="vLLM upstream returned error",
                    retryable=resp.status_code in self.retryable_status_codes,
                    status_code=resp.status_code,
                    response_body=resp.text,
                )

            data = resp.json()
            choices = data.get("choices") or []
            text = ""
            if choices and isinstance(choices[0], dict):
                message = choices[0].get("message") or {}
                text = message.get("content") or ""
            usage = data.get("usage") or {}
            output_tokens = int(
                usage.get("completion_tokens")
                or usage.get("output_tokens")
                or _estimate_output_tokens(text)
            )
            return VLLMResult(
                text=text,
                output_tokens=output_tokens,
                ttft_ms=None,
                usage=usage,
                model=data.get("model") or self.model,
            )
        except httpx.TimeoutException as exc:
            raise VLLMClientError(message="vLLM request timed out", retryable=True) from exc
        except httpx.RequestError as exc:
            raise VLLMClientError(message=f"vLLM request error: {exc}", retryable=True) from exc

    async def check_ready(self) -> Dict[str, Any]:
        try:
            resp = await self.client.get("/models")
            if resp.status_code >= 400:
                return {
                    "upstream_ok": False,
                    "model_loaded": False,
                    "status_code": resp.status_code,
                }

            data = resp.json() if resp.content else {}
            models = data.get("data") or []
            model_ids = [m.get("id") for m in models if isinstance(m, dict) and isinstance(m.get("id"), str)]
            model_loaded = self.model in model_ids if model_ids else True
            return {
                "upstream_ok": True,
                "model_loaded": bool(model_loaded),
                "model": self.model,
                "available_models": model_ids,
            }
        except Exception as exc:
            return {
                "upstream_ok": False,
                "model_loaded": False,
                "error": str(exc),
            }
