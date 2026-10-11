from __future__ import annotations

from datetime import datetime, timezone
from email.message import EmailMessage

from quant_options_monitor.alerts.base import AlertMessage
from quant_options_monitor.alerts.console import ConsoleAlertSender
from quant_options_monitor.alerts.email import EmailAlertSender, EmailAlertSettings
from quant_options_monitor.alerts.formatters import format_options_candidate_alert
from quant_options_monitor.alerts.telegram import TelegramAlertSender, TelegramAlertSettings
from quant_options_monitor.features.regime import MarketRegime, RegimeResult
from quant_options_monitor.options.mock_provider import MockOptionsProvider
from quant_options_monitor.options.selector import OptionsStrategySelectorSettings
from quant_options_monitor.options.strategies.call_spread import BullCallSpreadSelector


def alert() -> AlertMessage:
    return AlertMessage(
        title="Bull Call Spread Candidate",
        symbol="nvda",
        severity="INFO",
        body="Test alert body",
        metadata={"score": 88.5},
    )


def test_console_alert_sender_prints_clean_alert(capsys) -> None:
    ConsoleAlertSender().send_alert(alert())

    output = capsys.readouterr().out
    assert "[INFO] NVDA - Bull Call Spread Candidate" in output
    assert "Test alert body" in output
    assert "score: 88.5" in output


class FakeSMTP:
    instances: list["FakeSMTP"] = []

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.started_tls = False
        self.login_args: tuple[str, str] | None = None
        self.messages: list[EmailMessage] = []
        FakeSMTP.instances.append(self)

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.login_args = (username, password)

    def send_message(self, message: EmailMessage) -> None:
        self.messages.append(message)


def test_email_alert_sender_sends_with_mocked_smtp() -> None:
    FakeSMTP.instances.clear()
    sender = EmailAlertSender(
        EmailAlertSettings(
            smtp_host="smtp.example.com",
            smtp_port=2525,
            username="user",
            password="secret-password",
            from_address="alerts@example.com",
            to_addresses=["desk@example.com"],
        ),
        smtp_factory=FakeSMTP,
    )

    sender.send_alert(alert())

    smtp = FakeSMTP.instances[0]
    assert smtp.host == "smtp.example.com"
    assert smtp.port == 2525
    assert smtp.started_tls
    assert smtp.login_args == ("user", "secret-password")
    message = smtp.messages[0]
    assert message["Subject"] == "[INFO] NVDA - Bull Call Spread Candidate"
    assert "secret-password" not in message.as_string()
    assert "Test alert body" in message.get_content()


def test_email_alert_sender_disabled_when_config_missing() -> None:
    FakeSMTP.instances.clear()
    sender = EmailAlertSender(EmailAlertSettings(), smtp_factory=FakeSMTP)

    sender.send_alert(alert())

    assert FakeSMTP.instances == []


def test_telegram_alert_sender_posts_with_mocked_http() -> None:
    calls = []

    def fake_post(url: str, payload: dict[str, object], timeout_seconds: float) -> None:
        calls.append((url, payload, timeout_seconds))

    sender = TelegramAlertSender(
        TelegramAlertSettings(bot_token="token-secret", chat_id="12345", timeout_seconds=3.0),
        post_func=fake_post,
    )

    sender.send_alert(alert())

    url, payload, timeout_seconds = calls[0]
    assert url == "https://api.telegram.org/bottoken-secret/sendMessage"
    assert payload["chat_id"] == "12345"
    assert "Test alert body" in str(payload["text"])
    assert "token-secret" not in str(payload["text"])
    assert timeout_seconds == 3.0


def test_telegram_alert_sender_disabled_when_config_missing() -> None:
    calls = []
    sender = TelegramAlertSender(TelegramAlertSettings(), post_func=lambda *args: calls.append(args))

    sender.send_alert(alert())

    assert calls == []


def test_format_options_candidate_alert_contains_required_sections() -> None:
    option_chain = MockOptionsProvider(
        underlying_prices={"NVDA": 500.0},
        as_of=datetime(2026, 5, 26, tzinfo=timezone.utc),
    ).get_chain("NVDA")
    regime = RegimeResult(
        symbol="NVDA",
        regime=MarketRegime.BULLISH_TREND,
        trend_score=0.9,
        range_score=0.0,
        volatility_score=0.0,
        reasons=["Bullish test regime."],
    )
    candidate = BullCallSpreadSelector().select(
        "NVDA",
        option_chain.underlying_price,
        option_chain,
        regime,
        OptionsStrategySelectorSettings(),
    )
    assert candidate is not None

    output = format_options_candidate_alert(
        symbol="NVDA",
        latest_price=500.0,
        regime_result=regime,
        candidate=candidate,
    )

    assert "[OPTIONS SIGNAL] NVDA - Bull Call Spread Candidate" in output
    assert "Price:" in output
    assert "Regime:" in output
    assert "Trend Score:" in output
    assert "Strategy:" in output
    assert "Legs:" in output
    assert "Max Loss:" in output
    assert "Max Profit:" in output
    assert "Breakevens:" in output
    assert "Reasons:" in output
    assert "Warnings:" in output
