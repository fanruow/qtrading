from __future__ import annotations

import argparse

from src.live.paper_trader import PaperTrader
from src.utils.config import load_config, project_path
from src.utils.env import load_dotenv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/paper.yaml")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    load_dotenv(project_path(args.env_file))
    config = load_config(project_path(args.config))
    default_dry_run = bool(config["paper_trading"]["execution"].get("dry_run_default", True))
    dry_run = True if args.dry_run else default_dry_run
    if args.execute:
        dry_run = False
    trader = PaperTrader(config)
    result = trader.run(dry_run=dry_run, execute=bool(args.execute))
    print(f"Wrote orders preview: {project_path('outputs/orders_preview.csv')}")
    print(f"Preview orders: {len(result['orders_preview'])}")
    print(f"Submitted orders: {len(result['submitted_orders'])}")


if __name__ == "__main__":
    main()
