"""SMTP email alert sender."""

from __future__ import annotations

import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Callable

from quant_options_monitor.alerts.base import AlertMessage, BaseAlertSender


@dataclass(frozen=True)
class EmailAlertSettings:
    smtp_host: str | None = None
    smtp_port: int = 587
    username: str | None = None
    password: str | None = None
    from_address: str | None = None
    to_addresses: list[str] = field(default_factory=list)
    use_tls: bool = True


class EmailAlertSender(BaseAlertSender):
    """SMTP alert sender. Disabled when required settings are absent."""

    def __init__(
        self,
        settings: EmailAlertSettings,
        smtp_factory: Callable[[str, int], smtplib.SMTP] = smtplib.SMTP,
    ) -> None:
        self.settings = settings
        self.smtp_factory = smtp_factory

    @property
    def enabled(self) -> bool:
        return bool(
            self.settings.smtp_host
            and self.settings.from_address
            and self.settings.to_addresses
            and self.settings.username
            and self.settings.password
        )

    def send_alert(self, alert: AlertMessage) -> None:
        if not self.enabled:
            return

        assert self.settings.smtp_host is not None
        assert self.settings.from_address is not None
        assert self.settings.username is not None
        assert self.settings.password is not None

        message = EmailMessage()
        message["Subject"] = f"[{alert.severity}] {alert.symbol} - {alert.title}"
        message["From"] = self.settings.from_address
        message["To"] = ", ".join(self.settings.to_addresses)
        message.set_content(alert.body)

        with self.smtp_factory(self.settings.smtp_host, self.settings.smtp_port) as smtp:
            if self.settings.use_tls:
                smtp.starttls()
            smtp.login(self.settings.username, self.settings.password)
            smtp.send_message(message)
