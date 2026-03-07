from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal

import yaml


RouterMode = Literal["baseline", "stage_aware"]
ALLOWED_STAGES = {"planning", "synthesis", "refinement"}


@dataclass(frozen=True)
class PolicyDecision:
    mode: RouterMode
    name: str
    generation: Dict[str, Any]


class PolicyRouter:
    def __init__(self, config_path: Path, default_mode: str = "stage_aware"):
        self.config_path = Path(config_path)
        self.default_mode = default_mode if default_mode in {"baseline", "stage_aware"} else "stage_aware"
        self._config = self._load_config(self.config_path)

    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        if not config_path.exists():
            raise FileNotFoundError(f"policy config not found: {config_path}")
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError("policy config must be a YAML mapping")
        return raw

    def _normalize_mode(self, mode: str | None) -> RouterMode:
        chosen = (mode or self.default_mode or self._config.get("default_mode") or "stage_aware").strip().lower()
        if chosen not in {"baseline", "stage_aware"}:
            raise ValueError(f"unsupported router mode: {chosen}")
        return chosen  # type: ignore[return-value]

    def resolve(self, stage: str, mode: str | None = None) -> PolicyDecision:
        stage_norm = (stage or "").strip().lower()
        if stage_norm not in ALLOWED_STAGES:
            raise ValueError(f"unsupported stage: {stage}")

        router_mode = self._normalize_mode(mode)
        if router_mode == "baseline":
            baseline = self._config.get("baseline") or {}
            name = str(baseline.get("name") or "baseline_shared")
            generation = baseline.get("generation") or {}
            return PolicyDecision(mode=router_mode, name=name, generation=self._sanitize_generation(generation))

        stage_cfg = ((self._config.get("stage_aware") or {}).get(stage_norm)) or {}
        name = str(stage_cfg.get("name") or f"{stage_norm}_default")
        generation = stage_cfg.get("generation") or {}
        return PolicyDecision(mode=router_mode, name=name, generation=self._sanitize_generation(generation))

    def _sanitize_generation(self, generation: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(generation, dict):
            raise ValueError("generation config must be a mapping")
        allowed_keys = {
            "temperature",
            "max_tokens",
            "top_p",
            "presence_penalty",
            "frequency_penalty",
            "repetition_penalty",
            "stop",
        }
        out: Dict[str, Any] = {}
        for key, value in generation.items():
            if key in allowed_keys and value is not None:
                out[key] = value
        if "max_tokens" not in out:
            out["max_tokens"] = 256
        if "temperature" not in out:
            out["temperature"] = 0.2
        return out
