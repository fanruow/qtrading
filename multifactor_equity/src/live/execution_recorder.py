from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd


def write_execution_outputs(
    output_dir: str | Path,
    orders_preview: pd.DataFrame,
    submitted_orders: pd.DataFrame,
    rejected_orders: pd.DataFrame,
    current_vs_target: pd.DataFrame,
    dry_run: bool,
    execute: bool,
    account: dict | None = None,
) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    orders_preview.to_csv(output_dir / "orders_preview.csv", index=False)
    submitted_orders.to_csv(output_dir / "submitted_orders.csv", index=False)
    rejected_orders.to_csv(output_dir / "rejected_orders.csv", index=False)
    current_vs_target.to_csv(output_dir / "current_vs_target.csv", index=False)
    log = {
        "timestamp": datetime.utcnow().isoformat(),
        "dry_run": dry_run,
        "execute": execute,
        "orders_preview_count": int(len(orders_preview)),
        "submitted_orders_count": int(len(submitted_orders)),
        "rejected_orders_count": int(len(rejected_orders)),
        "account": account or {},
    }
    (output_dir / "paper_execution_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
