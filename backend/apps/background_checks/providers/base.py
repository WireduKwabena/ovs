from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ProviderSubmission:
    status: str
    external_reference: str
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderResult:
    status: str
    raw_payload: dict[str, Any] = field(default_factory=dict)
    score: float | None = None
    risk_level: str | None = None
    recommendation: str | None = None
    completed_at: datetime | None = None


class BackgroundCheckProvider(ABC):
    key = "base"

    @abstractmethod
    def submit_check(self, check) -> ProviderSubmission:
        raise NotImplementedError

    @abstractmethod
    def refresh_check(self, check) -> ProviderResult:
        raise NotImplementedError

    @abstractmethod
    def parse_webhook(self, payload: dict[str, Any]) -> ProviderResult:
        raise NotImplementedError
