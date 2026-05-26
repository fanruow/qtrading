"""Configuration models for the alert-only monitor."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional, Union

import yaml
from pydantic import BaseModel, Field


class EmailConfig(BaseModel):
    enabled: bool = False
    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587
    username_env: str = "QOM_EMAIL_USERNAME"
    password_env: str = "QOM_EMAIL_PASSWORD"
    from_address: str = "alerts@example.com"
    to_addresses: list[str] = Field(default_factory=list)


class TelegramConfig(BaseModel):
    enabled: bool = False
    bot_token_env: str = "QOM_TELEGRAM_BOT_TOKEN"
    chat_id_env: str = "QOM_TELEGRAM_CHAT_ID"


class RiskConfig(BaseModel):
    max_position_risk_pct: float = 0.01
    max_symbol_exposure_pct: float = 0.10
    max_portfolio_drawdown_pct: float = 0.20
    min_option_volume: int = 100
    min_option_open_interest: int = 500
    max_bid_ask_spread_pct: float = 0.12


class StrategyConfig(BaseModel):
    dte_min: int = 21
    dte_max: int = 60
    target_delta_long: float = 0.35
    target_delta_short: float = 0.20


class AppConfig(BaseModel):
    provider: Literal["yfinance"] = "yfinance"
    lookback_days: int = 252
    initial_capital: float = 100_000.0
    risk: RiskConfig = Field(default_factory=RiskConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)


def load_config(path: Union[str, Path] = "configs/example.yaml") -> AppConfig:
    """Load YAML configuration into validated pydantic settings."""

    config_path = Path(path)
    if not config_path.exists():
        return AppConfig()
    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return AppConfig.model_validate(data)
