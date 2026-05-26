# quant-options-monitor

Note: this directory now contains the earlier prototype CLI that imports `src.*`.
New implementation work should happen in the sibling `../quant_options_monitor/`
project, whose Python package is `quant_options_monitor`.

`quant-options-monitor` is a Python 3.11+ research and alerting system for equities and
multi-leg options strategies. Version 1 is intentionally alert-only: it does not place,
route, or manage real-money orders.

## Features

- Modular `src/` package structure
- Abstract `BaseMarketDataProvider` plus yfinance fallback provider
- Technical indicators: SMA, EMA, RSI, MACD, ATR, realized volatility, volume z-score
- Volatility features: IV rank, IV percentile, IV versus realized spread, term structure score, skew score
- Rule-based market regime classifier
- Options strategy candidates: bull call spread, bear put spread, calendar spread, butterfly, iron condor
- LightGBM ML wrapper, feature dataset builder, walk-forward validation, meta-labeling
- Risk controls for position risk, symbol exposure, portfolio drawdown, and option liquidity
- Console alerts, email alerts, and Telegram alert stub
- Equity signal backtest, options simulation stub, and performance metrics

## Setup

```bash
cd quant-options-monitor
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Example Scan

```bash
python -m src.app.scheduler --symbols SPY QQQ NVDA TSLA --mode scan
```

The scheduler uses `configs/example.yaml` by default. If live yfinance setup is unavailable,
tests and internal demos can use the deterministic synthetic provider.

## Configuration

See `configs/example.yaml` for all defaults.

Environment variables for optional email alerts:

- `QOM_EMAIL_USERNAME`
- `QOM_EMAIL_PASSWORD`

Environment variables for the Telegram stub:

- `QOM_TELEGRAM_BOT_TOKEN`
- `QOM_TELEGRAM_CHAT_ID`

## API

An optional FastAPI app is included:

```bash
uvicorn src.app.api:app --reload
```

Endpoints:

- `GET /health`
- `POST /scan` with a JSON list of symbols

## Tests

```bash
pytest
```

## Safety

This project is research and alerting software only. It contains no real-money order execution
or broker order routing in v1.
