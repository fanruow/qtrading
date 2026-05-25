from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def project_path(path: str | Path) -> Path:
    base = Path(__file__).resolve().parents[2]
    return (base / path).resolve()
