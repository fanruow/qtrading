# quant_options_monitor

This is the canonical Python package project for the options monitor work.

The sibling `quant-options-monitor/` directory contains the earlier prototype CLI
that imports `src.*`. New implementation work should target this directory and
the import package:

```python
import quant_options_monitor
```

## Test

```bash
cd /Users/fanruowang/GitHub/qtrading/quant_options_monitor
python3 -m pytest
```

## Scan

```bash
python3 -m quant_options_monitor.app.scheduler --symbols SPY QQQ NVDA TSLA --mode scan
```

The scan command currently uses deterministic mock market data and
`MockOptionsProvider`, so it runs without internet access.

## Equity Backtest

```bash
python3 -m quant_options_monitor.app.backtest --symbol SPY --period 5y
```

The equity backtester is intentionally simple:

- builds trailing technical features from OHLCV data
- generates the equity signal as of each historical bar
- applies the signal to the next bar to avoid lookahead bias
- simulates long/cash or short/cash exposure with no leverage by default
- subtracts transaction costs when position changes
- falls back to deterministic mock data if yfinance is unavailable

Limitations:

- daily close-to-close simulation only
- no intraday fills, slippage model, borrow cost, dividends, or tax handling
- strategy logic is rule-based and intended for research, not execution
- historical backtest results are not trading recommendations

## Current Modules

- `quant_options_monitor.app`
- `quant_options_monitor.backtest`
- `quant_options_monitor.data`
- `quant_options_monitor.features`
- `quant_options_monitor.options`
- `quant_options_monitor.risk`
- `quant_options_monitor.strategies`
