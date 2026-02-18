from __future__ import annotations

from abc import ABC, abstractmethod


class EmailProvider(ABC):
    @abstractmethod
    def send(self, *, to: str, subject: str, html: str) -> str:
        raise NotImplementedError
