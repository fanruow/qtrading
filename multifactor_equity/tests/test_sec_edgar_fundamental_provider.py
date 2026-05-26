from __future__ import annotations

import pandas as pd

from src.data.providers.sec_edgar_fundamental import SECEdgarFundamentalProvider, STANDARD_FUNDAMENTAL_COLUMNS


def companyfacts_payload():
    def unit(vals):
        return {"units": {"USD": vals}}

    quarterly = [
        {"end": "2023-03-31", "filed": "2023-05-01", "val": 10, "form": "10-Q", "fp": "Q1"},
        {"end": "2023-06-30", "filed": "2023-08-01", "val": 20, "form": "10-Q", "fp": "Q2"},
        {"end": "2023-09-30", "filed": "2023-11-01", "val": 30, "form": "10-Q", "fp": "Q3"},
        {"end": "2023-12-31", "filed": "2024-02-15", "val": 40, "form": "10-K", "fp": "Q4"},
    ]
    return {
        "facts": {
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {
                        "shares": [
                            {"end": "2023-12-31", "filed": "2024-02-15", "val": 100, "form": "10-K", "fp": "FY"}
                        ]
                    }
                }
            },
            "us-gaap": {
                "NetIncomeLoss": unit(quarterly),
                "Revenues": unit([{**row, "val": row["val"] * 10} for row in quarterly]),
                "GrossProfit": unit([{**row, "val": row["val"] * 4} for row in quarterly]),
                "NetCashProvidedByUsedInOperatingActivities": unit([{**row, "val": row["val"] * 2} for row in quarterly]),
                "PaymentsToAcquirePropertyPlantAndEquipment": unit([{**row, "val": row["val"]} for row in quarterly]),
                "Assets": unit([{"end": "2023-12-31", "filed": "2024-02-15", "val": 1000, "form": "10-K", "fp": "FY"}]),
                "StockholdersEquity": unit([{"end": "2023-12-31", "filed": "2024-02-15", "val": 400, "form": "10-K", "fp": "FY"}]),
                "LongTermDebtCurrent": unit([{"end": "2023-12-31", "filed": "2024-02-15", "val": 50, "form": "10-K", "fp": "FY"}]),
                "LongTermDebtNoncurrent": unit([{"end": "2023-12-31", "filed": "2024-02-15", "val": 150, "form": "10-K", "fp": "FY"}]),
            }
        }
    }


class StubSECEdgarProvider(SECEdgarFundamentalProvider):
    def _load_ticker_cik_map(self):
        return {"AAA": "0000000001"}

    def _load_companyfacts(self, ticker, cik):
        return companyfacts_payload()


def test_sec_edgar_provider_standardizes_fields_and_date_range(tmp_path):
    provider = StubSECEdgarProvider(tickers=["AAA"], start="2023-12-01", end="2023-12-31", cache_dir=tmp_path)

    df = provider.load_fundamentals()

    assert set(STANDARD_FUNDAMENTAL_COLUMNS).issubset(df.columns)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["ticker"] == "AAA"
    assert row["period_end"] == pd.Timestamp("2023-12-31")
    assert row["available_date"] == pd.Timestamp("2024-02-15")
    assert row["net_income_ttm"] == 100
    assert row["revenue_ttm"] == 1000
    assert row["gross_profit_ttm"] == 400
    assert row["operating_cash_flow_ttm"] == 200
    assert row["free_cash_flow_ttm"] == 100
    assert row["book_equity"] == 400
    assert row["total_assets"] == 1000
    assert row["total_debt"] == 200
    assert row["shares_outstanding"] == 100


def test_sec_edgar_provider_asof_uses_available_date(tmp_path):
    provider = StubSECEdgarProvider(tickers=["AAA"], start="2023-12-01", end="2023-12-31", cache_dir=tmp_path)

    before_filing = provider.fundamentals_asof(pd.Timestamp("2024-01-31"))
    after_filing = provider.fundamentals_asof(pd.Timestamp("2024-02-16"))

    assert before_filing.empty
    assert after_filing.loc["AAA", "available_date"] == pd.Timestamp("2024-02-15")


def test_sec_edgar_provider_writes_standardized_cache(tmp_path):
    provider = StubSECEdgarProvider(tickers=["AAA"], start="2023-12-01", end="2023-12-31", cache_dir=tmp_path, cache_enabled=True)

    provider.load_fundamentals()

    assert list(tmp_path.glob("standardized_AAA_2023-12-01_2023-12-31.csv"))
