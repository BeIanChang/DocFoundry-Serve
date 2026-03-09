from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class ServiceError(Exception):
    pass


class AuthError(ServiceError):
    pass


class AdmissionError(ServiceError):
    pass


class QueueFullError(AdmissionError):
    pass


class QueueTimeoutError(AdmissionError):
    pass


class StageOverloadedError(AdmissionError):
    pass


class TimeoutBudgetExceededError(ServiceError):
    pass


@dataclass
class VLLMClientError(ServiceError):
    message: str
    retryable: bool = False
    status_code: Optional[int] = None
    response_body: Optional[str] = None

    def __str__(self) -> str:
        if self.status_code is not None:
            return f"{self.message} (status={self.status_code})"
        return self.message


class VLLMRetryExhaustedError(VLLMClientError):
    attempts: int = 1
