"""Base alert message and sender contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertMessage(BaseModel):
    """Structured alert payload shared by all senders."""

    model_config = ConfigDict(use_enum_values=True)

    title: str
    symbol: str
    severity: AlertSeverity = AlertSeverity.INFO
    body: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "symbol", "body")
    @classmethod
    def not_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("alert text fields must not be empty")
        return value

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper()


class BaseAlertSender(ABC):
    """Interface for alert delivery channels."""

    @abstractmethod
    def send_alert(self, alert: AlertMessage) -> None:
        """Send one alert message."""
