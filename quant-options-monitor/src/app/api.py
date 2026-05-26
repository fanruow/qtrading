"""Optional FastAPI surface for running scans."""

from __future__ import annotations

from fastapi import FastAPI

from src.app.scheduler import scan_symbols
from src.config import load_config

app = FastAPI(title="Quant Options Monitor")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/scan")
def scan(symbols: list[str]) -> dict[str, list[str]]:
    return {"alerts": scan_symbols(symbols, load_config())}
