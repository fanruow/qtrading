"""Telegram bot alert sender."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable
from urllib import request

from quant_options_monitor.alerts.base import AlertMessage, BaseAlertSender


@dataclass(frozen=True)
class TelegramAlertSettings:
    bot_token: str | None = None
    chat_id: str | None = None
    timeout_seconds: float = 10.0


PostFunc = Callable[[str, dict[str, object], float], None]


class TelegramAlertSender(BaseAlertSender):
    """Telegram bot sender. Disabled when token or chat_id is missing."""

    def __init__(
        self,
        settings: TelegramAlertSettings,
        post_func: PostFunc | None = None,
    ) -> None:
        self.settings = settings
        self.post_func = post_func or _post_json

    @property
    def enabled(self) -> bool:
        return bool(self.settings.bot_token and self.settings.chat_id)

    def send_alert(self, alert: AlertMessage) -> None:
        if not self.enabled:
            return
        assert self.settings.bot_token is not None
        assert self.settings.chat_id is not None

        url = f"https://api.telegram.org/bot{self.settings.bot_token}/sendMessage"
        payload = {
            "chat_id": self.settings.chat_id,
            "text": f"[{alert.severity}] {alert.symbol} - {alert.title}\n\n{alert.body}",
            "disable_web_page_preview": True,
        }
        self.post_func(url, payload, self.settings.timeout_seconds)


def _post_json(url: str, payload: dict[str, object], timeout_seconds: float) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout_seconds) as response:
        response.read()
