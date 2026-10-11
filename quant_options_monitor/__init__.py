"""Repository-root import shim for the src-layout package."""

from __future__ import annotations

from pathlib import Path


src_package = Path(__file__).resolve().parent / "src" / "quant_options_monitor"
if src_package.exists():
    __path__ = [str(src_package)]
