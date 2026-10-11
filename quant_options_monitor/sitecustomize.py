"""Local development path bootstrap for running modules from the repo checkout."""

from __future__ import annotations

import sys
from pathlib import Path


src_path = Path(__file__).resolve().parent / "src"
if src_path.exists() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
