"""Alert delivery channels."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Protocol

from src.config import EmailConfig, TelegramConfig


class AlertChannel(Protocol):
    def send(self, subject: str, body: str) -> None:
        """Send an alert."""


class ConsoleAlert:
    def send(self, subject: str, body: str) -> None:
        print(f"\n=== {subject} ===\n{body}\n")


class EmailAlert:
    def __init__(self, config: EmailConfig) -> None:
        self.config = config

    def send(self, subject: str, body: str) -> None:
        if not self.config.enabled:
            return
        username = os.getenv(self.config.username_env)
        password = os.getenv(self.config.password_env)
        if not username or not password or not self.config.to_addresses:
            raise RuntimeError("Email alerting enabled but credentials or recipients are missing")
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.config.from_address
        msg["To"] = ", ".join(self.config.to_addresses)
        msg.set_content(body)
        with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(msg)


class TelegramAlert:
    """Stub for Telegram alerting. Network delivery is intentionally omitted in v1."""

    def __init__(self, config: TelegramConfig) -> None:
        self.config = config

    def send(self, subject: str, body: str) -> None:
        if self.config.enabled:
            print(f"[telegram stub] {subject}: {body[:200]}")


class AlertRouter:
    def __init__(self, channels: list[AlertChannel]) -> None:
        self.channels = channels

    def send(self, subject: str, body: str) -> None:
        for channel in self.channels:
            channel.send(subject, body)
