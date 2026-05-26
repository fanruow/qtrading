from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from src.data.providers.base import FundamentalDataProvider


STANDARD_FUNDAMENTAL_COLUMNS = [
    "ticker",
    "report_date",
    "available_date",
    "period_end",
    "sector",
    "market_cap",
    "enterprise_value",
    "net_income_ttm",
    "free_cash_flow_ttm",
    "book_value",
    "book_equity",
    "revenue_ttm",
    "gross_profit_ttm",
    "operating_cash_flow_ttm",
    "total_assets",
    "total_debt",
]


CONCEPT_MAP = {
    "shares_outstanding": ["EntityCommonStockSharesOutstanding"],
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
    "gross_profit": ["GrossProfit"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "assets": ["Assets"],
    "book_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "debt_current": [
        "ShortTermBorrowings",
        "LongTermDebtCurrent",
        "LongTermDebtAndFinanceLeaseObligationsCurrent",
    ],
    "debt_noncurrent": [
        "LongTermDebtNoncurrent",
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
        "LongTermDebt",
    ],
}


class SECEdgarFundamentalProvider(FundamentalDataProvider):
    def __init__(
        self,
        tickers: list[str] | None = None,
        start: str | None = None,
        end: str | None = None,
        cache_dir: str | Path = "data/cache/fundamentals",
        user_agent: str | None = None,
        cache_enabled: bool = True,
    ):
        self.tickers = tickers or []
        self.start = start
        self.end = end
        self.cache_dir = Path(cache_dir)
        self.user_agent = user_agent or os.environ.get("SEC_USER_AGENT", "multifactor-equity research contact@example.com")
        self.cache_enabled = cache_enabled
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def load_fundamentals(self) -> pd.DataFrame:
        if not self.tickers:
            return pd.DataFrame(columns=STANDARD_FUNDAMENTAL_COLUMNS)
        return self.fetch_fundamentals(self.tickers, self.start, self.end)

    def fetch_fundamentals(self, tickers: list[str], start: str | None = None, end: str | None = None) -> pd.DataFrame:
        rows = []
        ticker_cik = self._load_ticker_cik_map()
        for ticker in tickers:
            cik = ticker_cik.get(ticker.upper())
            if cik is None:
                continue
            payload = self._load_companyfacts(ticker.upper(), cik)
            rows.extend(self._standardize_companyfacts(ticker.upper(), payload, start, end))
        df = pd.DataFrame(
            rows,
            columns=STANDARD_FUNDAMENTAL_COLUMNS
            + ["shares_outstanding", "security_type", "is_adr", "is_etf", "is_otc", "is_preferred"],
        )
        if df.empty:
            return df
        for col in ["report_date", "available_date", "period_end"]:
            df[col] = pd.to_datetime(df[col])
        df = df.sort_values(["ticker", "available_date", "period_end"]).reset_index(drop=True)
        self._write_standardized_cache(df, tickers, start, end)
        return df

    def _request_json(self, url: str) -> dict[str, Any]:
        request = Request(url, headers={"User-Agent": self.user_agent, "Accept-Encoding": "identity"})
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def _load_ticker_cik_map(self) -> dict[str, str]:
        path = self.cache_dir / "company_tickers.json"
        if self.cache_enabled and path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
        else:
            payload = self._request_json("https://www.sec.gov/files/company_tickers.json")
            if self.cache_enabled:
                path.write_text(json.dumps(payload), encoding="utf-8")
        mapping = {}
        for row in payload.values():
            mapping[row["ticker"].upper()] = f"{int(row['cik_str']):010d}"
        return mapping

    def _load_companyfacts(self, ticker: str, cik: str) -> dict[str, Any]:
        path = self.cache_dir / f"{ticker}_{cik}_companyfacts.json"
        if self.cache_enabled and path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        payload = self._request_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
        if self.cache_enabled:
            path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def _standardize_companyfacts(self, ticker: str, payload: dict[str, Any], start: str | None, end: str | None) -> list[dict[str, Any]]:
        facts = payload.get("facts", {}).get("us-gaap", {})
        all_facts = facts | payload.get("facts", {}).get("dei", {})
        period_ends = sorted(set(self._concept_frame(facts, "net_income")["end"].dropna()))
        rows = []
        start_ts = pd.Timestamp(start) if start else None
        end_ts = pd.Timestamp(end) if end else None
        for period_end in period_ends:
            period_ts = pd.Timestamp(period_end)
            if start_ts is not None and period_ts < start_ts:
                continue
            if end_ts is not None and period_ts > end_ts:
                continue
            row = self._row_for_period(ticker, facts, all_facts, period_ts)
            if row is not None:
                rows.append(row)
        return rows

    def _row_for_period(self, ticker: str, facts: dict[str, Any], all_facts: dict[str, Any], period_end: pd.Timestamp) -> dict[str, Any] | None:
        net_income = self._ttm_value(facts, "net_income", period_end)
        if pd.isna(net_income):
            return None
        revenue = self._ttm_value(facts, "revenue", period_end)
        gross_profit = self._ttm_value(facts, "gross_profit", period_end)
        ocf = self._ttm_value(facts, "operating_cash_flow", period_end)
        capex = self._ttm_value(facts, "capex", period_end)
        assets = self._point_value(facts, "assets", period_end)
        equity = self._point_value(facts, "book_equity", period_end)
        debt_current = self._point_value(facts, "debt_current", period_end)
        debt_noncurrent = self._point_value(facts, "debt_noncurrent", period_end)
        shares_outstanding = self._point_value(all_facts, "shares_outstanding", period_end)
        filed = self._available_date(facts, period_end)
        total_debt = self._nan_to_zero(debt_current) + self._nan_to_zero(debt_noncurrent)
        return {
            "ticker": ticker,
            "report_date": filed,
            "available_date": filed,
            "period_end": period_end,
            "sector": "Unknown",
            "market_cap": pd.NA,
            "enterprise_value": pd.NA,
            "net_income_ttm": net_income,
            "free_cash_flow_ttm": ocf - capex if pd.notna(ocf) and pd.notna(capex) else pd.NA,
            "book_value": equity,
            "book_equity": equity,
            "revenue_ttm": revenue,
            "gross_profit_ttm": gross_profit,
            "operating_cash_flow_ttm": ocf,
            "total_assets": assets,
            "total_debt": total_debt if total_debt != 0 else pd.NA,
            "shares_outstanding": shares_outstanding,
            "security_type": "Common Stock",
            "is_adr": False,
            "is_etf": False,
            "is_otc": False,
            "is_preferred": False,
        }

    def _concept_frame(self, facts: dict[str, Any], logical_name: str) -> pd.DataFrame:
        frames = []
        for concept in CONCEPT_MAP[logical_name]:
            units = facts.get(concept, {}).get("units", {})
            for unit, records in units.items():
                if unit != "USD" and logical_name != "shares_outstanding":
                    continue
                frame = pd.DataFrame(records)
                if not frame.empty:
                    frame["concept"] = concept
                    frames.append(frame)
        if not frames:
            return pd.DataFrame(columns=["end", "filed", "val", "form", "fp"])
        frame = pd.concat(frames, ignore_index=True)
        for col in ["end", "filed"]:
            frame[col] = pd.to_datetime(frame[col], errors="coerce")
        frame["val"] = pd.to_numeric(frame["val"], errors="coerce")
        return frame.dropna(subset=["end", "filed", "val"]).sort_values(["end", "filed"])

    def _ttm_value(self, facts: dict[str, Any], logical_name: str, period_end: pd.Timestamp) -> float:
        frame = self._concept_frame(facts, logical_name)
        if frame.empty:
            return pd.NA
        frame = frame[(frame["end"] <= period_end) & (frame["end"] > period_end - pd.DateOffset(months=15))]
        if "fp" in frame.columns:
            q_frame = frame[frame["fp"].isin(["Q1", "Q2", "Q3", "Q4"])]
            if len(q_frame) >= 4:
                return float(q_frame.drop_duplicates("end", keep="last").tail(4)["val"].sum())
        annual = frame[frame.get("form", pd.Series(index=frame.index)).isin(["10-K", "10-K/A"])]
        if not annual.empty:
            return float(annual.drop_duplicates("end", keep="last").iloc[-1]["val"])
        return float(frame.drop_duplicates("end", keep="last").tail(4)["val"].sum())

    def _point_value(self, facts: dict[str, Any], logical_name: str, period_end: pd.Timestamp) -> float:
        frame = self._concept_frame(facts, logical_name)
        frame = frame[frame["end"] <= period_end] if not frame.empty else frame
        if frame.empty:
            return pd.NA
        return float(frame.drop_duplicates("end", keep="last").iloc[-1]["val"])

    def _available_date(self, facts: dict[str, Any], period_end: pd.Timestamp) -> pd.Timestamp:
        dates = []
        for logical_name in ["net_income", "revenue", "assets", "book_equity"]:
            frame = self._concept_frame(facts, logical_name)
            frame = frame[frame["end"] == period_end] if not frame.empty else frame
            if not frame.empty:
                dates.append(frame["filed"].max())
        return max(dates) if dates else period_end

    def _write_standardized_cache(self, df: pd.DataFrame, tickers: list[str], start: str | None, end: str | None) -> None:
        if not self.cache_enabled or df.empty:
            return
        name = "_".join(sorted(t.upper() for t in tickers))
        suffix = f"{start or 'start'}_{end or 'end'}".replace("/", "-")
        df.to_csv(self.cache_dir / f"standardized_{name}_{suffix}.csv", index=False)

    @staticmethod
    def _nan_to_zero(value: Any) -> float:
        return 0.0 if pd.isna(value) else float(value)


FundamentalProvider = SECEdgarFundamentalProvider
