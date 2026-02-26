from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypedDict


class SMSProviderError(RuntimeError):
    pass


class SMSProviderResult(TypedDict):
    messageId: str


class SMSProvider(ABC):
    @abstractmethod
    def send(self, *, to: str, body: str) -> SMSProviderResult:
        raise NotImplementedError

    @abstractmethod
    def check_health(self, *, timeout_seconds: float) -> str:
        raise NotImplementedError
