"""Console alert sender."""

from __future__ import annotations

from quant_options_monitor.alerts.base import AlertMessage, BaseAlertSender


class ConsoleAlertSender(BaseAlertSender):
    """Print clean formatted alerts to stdout."""

    def send_alert(self, alert: AlertMessage) -> None:
        print(_format_console_alert(alert))


def _format_console_alert(alert: AlertMessage) -> str:
    lines = [
        f"[{alert.severity}] {alert.symbol} - {alert.title}",
        alert.body,
    ]
    if alert.metadata:
        lines.append("Metadata:")
        for key, value in sorted(alert.metadata.items()):
            lines.append(f"  {key}: {value}")
    return "\n".join(lines)
