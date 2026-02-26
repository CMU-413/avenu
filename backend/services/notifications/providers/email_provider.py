from __future__ import annotations

from abc import ABC, abstractmethod


class MailProviderError(RuntimeError):
    pass


class EmailProvider(ABC):
    @abstractmethod
    def send(self, *, to: str, subject: str, html: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def check_health(self, *, timeout_seconds: float) -> str:
        raise NotImplementedError
