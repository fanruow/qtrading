from __future__ import annotations

import argparse

import pandas as pd

from src.paper_trading.alpaca import AlpacaPaperBroker
from src.paper_trading.runner import PaperTradingRunner
from src.utils.config import load_config, project_path
from src.utils.env import load_dotenv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--factor-scores", default="outputs/factor_scores.csv")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=None)
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    args = parser.parse_args()

    load_dotenv(project_path(args.env_file))
    config = load_config(project_path(args.config))
    paper_cfg = dict(config.get("paper_trading", {}))
    if args.dry_run is not None:
        paper_cfg["dry_run"] = args.dry_run
    paper_cfg["execute"] = bool(args.execute)
    config["paper_trading"] = paper_cfg

    factor_scores = pd.read_csv(project_path(args.factor_scores))
    broker = None
    if args.execute:
        broker = AlpacaPaperBroker()
    runner = PaperTradingRunner(config, broker=broker, output_dir=project_path("outputs"))
    result = runner.run_from_factor_scores(factor_scores)
    print(f"Wrote orders preview: {project_path('outputs/orders_preview.csv')}")
    print(f"Orders in preview: {len(result['orders_preview'])}")
    if args.execute:
        print(f"Submitted paper orders: {len(result['submitted_orders'])}")


if __name__ == "__main__":
    main()
