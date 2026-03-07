from __future__ import annotations

from dataclasses import dataclass
import json
import math
import time
from typing import Any, Dict, Optional

import httpx


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
    def __init__(self, *, base_url: str, model: str, timeout_seconds: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout_seconds)

    async def close(self) -> None:
        await self.client.aclose()

    async def generate(self, *, prompt: str, generation: Dict[str, Any]) -> VLLMResult:
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
                resp.raise_for_status()
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
        except Exception:
            fallback_payload = dict(payload)
            fallback_payload["stream"] = False
            fallback_payload.pop("stream_options", None)

            resp = await self.client.post("/chat/completions", json=fallback_payload)
            resp.raise_for_status()
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
