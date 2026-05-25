# ETF Dual Momentum Research Backtester

This project implements a research-only Python backtest for an ETF dual momentum strategy with volatility targeting, monthly rebalancing, transaction costs, and benchmark comparison.

It does not connect to live trading APIs, does not forecast next-day returns, and does not optimize parameters on the full sample.

## Strategy

- Universe: `SPY QQQ IWM EFA EEM TLT IEF GLD VNQ DBC`
- Data: adjusted close from Yahoo Finance via `yfinance`
- Signal dates: last trading day of each month
- Execution: next trading day after each signal date
- Momentum: `adjusted_close[t-21] / adjusted_close[t-252] - 1`
- Absolute momentum filters:
  - momentum > 0
  - adjusted close > 200-day moving average
- Select top 3 passing ETFs by momentum
- Equal-weight selected ETFs
- If fewer than 3 pass, unallocated capital stays in cash
- Cash return is assumed to be 0
- Volatility target:
  - realized vol = trailing 63-day strategy return std * `sqrt(252)`
  - target vol = 10%
  - scale is clipped to `[0, 1]`
  - scaled weights are applied on rebalance execution dates using only information available before execution
- Trading cost:
  - turnover = `sum(abs(new_weight - old_weight))`
  - rebalance cost = `turnover * 0.001`
  - cost is deducted from strategy return on the rebalance execution day

## Project Structure

```text
quant_dual_momentum/
  README.md
  requirements.txt
  main.py
  src/
    data.py
    signals.py
    portfolio.py
    backtest.py
    metrics.py
    benchmarks.py
    plotting.py
    utils.py
    execution/
      broker_base.py
      alpaca_broker.py
      order_manager.py
    risk/
      pre_trade_checks.py
      limits.py
      kill_switch.py
    state/
      store.py
      reconciliation.py
    live/
      run_daily_rebalance.py
      scheduler.py
  tests/
    test_signals.py
    test_portfolio.py
    test_metrics.py
    test_backtest.py
    test_execution.py
```

## Setup

```bash
cd quant_dual_momentum
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
# or, on systems where Python is exposed as python3:
python3 main.py
```

Outputs are written to `outputs/`:

- `equity_curves.csv`
- `weights.csv`
- `rebalance_log.csv`
- `performance_summary.csv`
- `equity_curve.png`
- `drawdown.png`

## Tests

```bash
pytest
# or:
python3 -m pytest
```

## Alpaca Paper Trading

This project includes a paper trading execution layer for Alpaca. It is intentionally restricted to paper trading and does not support live trading.

Create a local `.env` file from `.env.example`:

```bash
cp .env.example .env
```

Then add your Alpaca paper credentials:

```text
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
```

Default `config.yaml` safety settings:

- `dry_run: true`
- `paper: true`
- `paper: false` is rejected by the broker adapter
- no order is submitted unless `--execute` is passed

Generate planned orders without submitting:

```bash
python -m src.live.run_daily_rebalance --dry-run
```

Submit to Alpaca paper trading only:

```bash
python -m src.live.run_daily_rebalance --paper --execute
```

The live path keeps strategy and execution separated:

- `src.signals` generates target weights
- `src.execution` converts target weights into share orders and submits or prints them
- `src.risk` blocks stale data, oversized orders, excessive position weights, live trading, missing account state, and abnormal order counts
- `src.state` writes run logs and `outputs/live_orders.csv`

Each run records timestamp, account equity, current positions, target weights, generated orders, submitted orders, and errors in `logs/`.

Generated live order rows are appended to `outputs/live_orders.csv`.

## Missing Data Policy

Yahoo adjusted close data is downloaded by ticker and aligned into one price table. The project does not forward-fill prices before an ETF exists. Asset returns are only calculated where both current and previous adjusted closes exist. Indicators require their own lookback windows, so the backtest naturally starts after all required data for an eligible signal exists. If an ETF lacks enough data on a signal date, it fails the indicator availability requirement for that date.

## Known Limitations

- Yahoo Finance data can be revised and may occasionally fail to download.
- Cash return is modeled as 0.
- No tax, slippage model, bid/ask spread model, borrow cost, or market impact.
- Benchmark 60/40 and equal-weight portfolios rebalance monthly with the same adjusted-close return convention.
- Monthly returns heatmap is intentionally omitted in this first version.
- The paper trading freshness check uses recent business-day data from Yahoo Finance and does not include a full exchange holiday calendar.
