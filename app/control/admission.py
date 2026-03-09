from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Optional

from app.errors import QueueFullError, QueueTimeoutError, StageOverloadedError


@dataclass(frozen=True)
class AdmissionSnapshot:
    max_in_flight: int
    in_flight: int
    waiting: int
    max_queue: int
    stage_in_flight: Dict[str, int]
    stage_waiting: Dict[str, int]


class AdmissionLease:
    def __init__(self, controller: "AdmissionController", stage: str):
        self._controller = controller
        self._stage = stage
        self._released = False

    async def release(self) -> None:
        if self._released:
            return
        self._released = True
        await self._controller._release(self._stage)


class AdmissionController:
    def __init__(
        self,
        *,
        max_in_flight: int,
        max_queue: int,
        queue_wait_timeout_seconds: float,
        stage_queue_limits: Optional[Dict[str, int]] = None,
        stage_in_flight_limits: Optional[Dict[str, int]] = None,
    ):
        self.max_in_flight = max(1, int(max_in_flight))
        self.max_queue = max(0, int(max_queue))
        self.queue_wait_timeout_seconds = max(0.001, float(queue_wait_timeout_seconds))
        self._global_sem = asyncio.Semaphore(self.max_in_flight)
        self._lock = asyncio.Lock()

        self._waiting = 0
        self._in_flight = 0
        self._stage_waiting = defaultdict(int)
        self._stage_in_flight = defaultdict(int)

        self._stage_queue_limits = {k: int(v) for k, v in (stage_queue_limits or {}).items()}
        self._stage_in_flight_limits = {k: int(v) for k, v in (stage_in_flight_limits or {}).items()}

    async def acquire(self, stage: str) -> AdmissionLease:
        stage_norm = (stage or "unknown").strip().lower() or "unknown"
        await self._enqueue(stage_norm)

        acquired = False
        try:
            await asyncio.wait_for(self._global_sem.acquire(), timeout=self.queue_wait_timeout_seconds)
            acquired = True
        except asyncio.TimeoutError as exc:
            raise QueueTimeoutError("queue wait timeout exceeded") from exc
        finally:
            await self._dequeue(stage_norm)

        if not acquired:
            raise QueueTimeoutError("failed to acquire worker slot")

        async with self._lock:
            stage_limit = self._stage_in_flight_limits.get(stage_norm)
            if stage_limit is not None and self._stage_in_flight[stage_norm] >= stage_limit:
                self._global_sem.release()
                raise StageOverloadedError(f"stage '{stage_norm}' is overloaded")
            self._in_flight += 1
            self._stage_in_flight[stage_norm] += 1

        return AdmissionLease(self, stage_norm)

    async def _enqueue(self, stage: str) -> None:
        async with self._lock:
            if self._waiting >= self.max_queue:
                raise QueueFullError("request queue is full")

            stage_limit = self._stage_queue_limits.get(stage)
            if stage_limit is not None and self._stage_waiting[stage] >= stage_limit:
                raise StageOverloadedError(f"stage '{stage}' queue is full")

            self._waiting += 1
            self._stage_waiting[stage] += 1

    async def _dequeue(self, stage: str) -> None:
        async with self._lock:
            self._waiting = max(0, self._waiting - 1)
            self._stage_waiting[stage] = max(0, self._stage_waiting[stage] - 1)

    async def _release(self, stage: str) -> None:
        async with self._lock:
            self._in_flight = max(0, self._in_flight - 1)
            self._stage_in_flight[stage] = max(0, self._stage_in_flight[stage] - 1)
        self._global_sem.release()

    async def snapshot(self) -> AdmissionSnapshot:
        async with self._lock:
            return AdmissionSnapshot(
                max_in_flight=self.max_in_flight,
                in_flight=self._in_flight,
                waiting=self._waiting,
                max_queue=self.max_queue,
                stage_in_flight=dict(self._stage_in_flight),
                stage_waiting=dict(self._stage_waiting),
            )
