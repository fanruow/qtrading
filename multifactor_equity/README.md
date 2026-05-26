# Multifactor Equity Research

Python 3.11+ long-only US equity multifactor research project. It implements a monthly rebalance strategy using Momentum, Value, Quality, and Low Volatility factors, with daily backtest accounting and basic factor diagnostics.

This is a research/backtest project only. It has no live trading integration.

## Quick Start

```bash
cd multifactor_equity
python main.py --config config.yaml
pytest
```

Default config uses deterministic mock prices so the example runs without network access. Set `data.price_provider: yfinance` or `data.price_provider: alpaca` in `config.yaml` to prototype external daily price data; keep `data.fundamental_provider: csv` for local CSV/parquet fundamentals.

## Paper Trading

The paper trading layer is isolated from the research/backtest engine. It reads the latest `outputs/factor_scores.csv`, rebuilds target weights with the same portfolio construction code, applies paper-trading risk checks, writes `outputs/orders_preview.csv`, and writes `outputs/paper_order_explanations.csv`.

Dry-run is the default:

```bash
python paper_trading.py --config config.yaml
```

Actual paper order submission requires both an explicit execute flag and disabling dry-run. Put paper keys in `multifactor_equity/.env`:

```bash
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
ALPACA_PAPER_BASE_URL=https://paper-api.alpaca.markets
```

Then run:

```bash
python paper_trading.py --config config.yaml --execute --no-dry-run
```

`.env` is ignored by git. Keys are loaded into environment variables at runtime and are never hardcoded. The Alpaca broker implementation rejects non-paper endpoints. Risk checks enforce long-only targets, no leverage after the configured cash buffer, max single-name weight, max sector weight, and unknown-symbol rejection.

`live_paper.py` is the automated Alpaca paper execution entrypoint. `main.py` never submits orders. The live paper runner reads `outputs/latest_target_portfolio.csv`, `outputs/latest_decisions.csv`, and `outputs/decision_explanations.csv`, syncs the Alpaca paper account, writes order/rejection/execution logs, and submits only when `--execute` is explicitly passed:

```bash
python live_paper.py --config configs/paper.yaml --dry-run
python live_paper.py --config configs/paper.yaml --execute
```

Stale signals are rejected when `paper_trading.risk.reject_if_stale_signal: true`.

## Decision Output

When `decision_output.enabled: true`, `main.py` also compares the latest target portfolio against `data/current_positions.csv` and writes the latest trading decision package. Current positions use:

```text
ticker,current_weight,current_shares
```

The decision layer classifies each ticker as `BUY`, `SELL`, `ADD`, `TRIM`, `HOLD`, or `SKIP`, attaches explanations derived only from existing `factor_scores` columns, and optionally writes an order preview. It never submits orders.

## Data Model

`data/fundamentals_sample.csv` is the first-version fundamental input, read by `CSVFundamentalProvider`. `LocalMetadataProvider` derives universe metadata from the same point-in-time file for the sample project. Required schema:

- `ticker`, `sector`, `security_type`
- `is_adr`, `is_etf`, `is_otc`, `is_preferred`
- `report_date`, `available_date`
- `market_cap`, `enterprise_value`
- `net_income_ttm`, `free_cash_flow_ttm`, `book_value`, `book_equity`
- `revenue_ttm`, `gross_profit_ttm`, `total_debt`, `operating_cash_flow_ttm`, `total_assets`

The backtest uses provider interfaces only for data access:

- `PriceDataProvider`
- `FundamentalDataProvider`
- `MetadataProvider`

The sample providers use only rows with `available_date <= signal_date`; `report_date` is metadata and should be retained for auditability. Real data should replace the sample providers with point-in-time, survivorship-bias-free fundamentals and security master data from sources such as Compustat, FactSet, Polygon, QuantConnect, OpenBB, or SEC EDGAR-derived pipelines. For production-grade research, include delisted names, historical sector/security classifications, split-adjusted prices, and actual historical tradability.

`SECEdgarFundamentalProvider` can be selected with `data.fundamental_provider: sec_edgar`. It calls SEC companyfacts by ticker/date range, maps differing XBRL concept names into the project schema, and caches raw and standardized data under `data/cache/fundamentals/`. SEC companyfacts does not provide sector, market cap, or enterprise value directly, so those fields are left missing unless another metadata/enrichment provider supplies them. If SEC `available_date` cannot be obtained from a richer filing feed, this provider uses companyfacts `filed` dates as `available_date`; this is conservative for look-ahead prevention but less precise than accepted datetime. The backtest still filters strictly on `available_date <= signal_date`.

## Strategy

- Eligible universe on each signal date:
  - US common stocks only
  - Exclude ETF, ADR, OTC, preferred shares
  - Price > 5
  - 20-day average dollar volume > 10,000,000
  - Market cap > 1,000,000,000
  - At least 252 trading days of price history
  - Fundamentals must be available before the signal date
  - No forward-filled pre-listing prices

- Signal date: monthly last trading day
- Execution date: next trading day
- Portfolio: top 50 by composite score, equal-weight seed, long-only, no leverage
- Constraints: max 2.5% per stock, max 25% per sector
- Costs: turnover * 0.10% commission plus turnover * 0.10% slippage

## Factors

- Momentum: `0.7 * zscore(mom_12_1) + 0.3 * zscore(mom_6_1)`, skipping the most recent 21 trading days
- Value: average z-score of earnings yield, FCF yield, book-to-market, sales-to-price
- Quality: average z-score of ROE, gross margin, negative debt-to-equity, negative accruals
- Low Volatility: average z-score of negative 63-day vol, negative 126-day vol, negative 252-day beta vs SPY

Each cross-section is winsorized and sector-neutral z-scored. Missing subfactors are averaged when enough data remains; `missing_count` columns are exported for audit.

## Outputs

All outputs are written to `outputs/`:

- `equity_curves.csv`
- `daily_returns.csv`
- `positions.csv`
- `trades.csv`
- `rebalance_log.csv`
- `factor_scores.csv`
- `factor_ic.csv`
- `factor_quantile_returns.csv`
- `decision_explanations.csv`
- `latest_rebalance_explanations.json`
- `orders_preview.csv`
- `paper_order_explanations.csv`
- `latest_decisions.csv`
- `latest_decisions.json`
- `latest_target_portfolio.csv`
- `current_vs_target.csv`
- `submitted_orders.csv`
- `rejected_orders.csv`
- `paper_execution_log.json`
- `performance_summary.csv`
- `sector_exposure.csv`
- `equity_curve.png`
- `drawdown.png`
- `factor_ic.png`

## Known Limits

The sample run is intentionally a small deterministic research harness. It is not a claim of tradable performance. Real research needs point-in-time security master data, delisting returns, survivorship-bias-free constituents, corporate action handling, reliable fundamentals availability timestamps, and liquidity/trading calendars from the chosen data vendor. No parameters are optimized on the full sample.
