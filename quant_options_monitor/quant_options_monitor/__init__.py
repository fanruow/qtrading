"""Development import shim for running the src-layout package without installation."""

from __future__ import annotations

from pathlib import Path


src_package = Path(__file__).resolve().parents[1] / "src" / "quant_options_monitor"
if src_package.exists():
    __path__ = [str(src_package)]
