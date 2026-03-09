import asyncio

import pytest

from app.control.admission import AdmissionController
from app.errors import QueueFullError


def test_admission_queue_full():
    async def _run() -> None:
        controller = AdmissionController(
            max_in_flight=1,
            max_queue=1,
            queue_wait_timeout_seconds=1.0,
            stage_queue_limits={"planning": 2},
            stage_in_flight_limits={"planning": 1},
        )

        lease = await controller.acquire("planning")
        try:
            waiting_task = asyncio.create_task(controller.acquire("planning"))
            await asyncio.sleep(0.05)
            with pytest.raises(QueueFullError):
                await controller.acquire("planning")

            waiting_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiting_task
        finally:
            await lease.release()

    asyncio.run(_run())


def test_admission_snapshot_updates():
    async def _run() -> None:
        controller = AdmissionController(
            max_in_flight=2,
            max_queue=4,
            queue_wait_timeout_seconds=1.0,
        )
        lease = await controller.acquire("synthesis")
        snap = await controller.snapshot()
        assert snap.in_flight == 1
        assert snap.stage_in_flight.get("synthesis") == 1
        await lease.release()

    asyncio.run(_run())
