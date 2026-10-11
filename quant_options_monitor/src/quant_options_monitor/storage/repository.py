"""SQLite repository for persisted signals and options candidates."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from quant_options_monitor.options.models import OptionStrategyCandidate
from quant_options_monitor.storage.models import (
    OPTION_CANDIDATES_INDEX_SQL,
    OPTION_CANDIDATES_TABLE_SQL,
    SIGNALS_INDEX_SQL,
    SIGNALS_TABLE_SQL,
)
from quant_options_monitor.strategies.equity_signal import EquitySignal


@dataclass(frozen=True)
class StoredSignalRecord:
    id: int
    timestamp: str
    symbol: str
    record_type: str
    name: str
    score: float
    payload: dict[str, Any]


class SQLiteSignalRepository:
    """Persist equity signals and option candidates to SQLite."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._initialize()

    def save_equity_signal(self, signal: EquitySignal, regime: str | None = None) -> int:
        payload_json = _model_to_json(signal)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO signals(timestamp, symbol, signal_type, regime, score, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    signal.timestamp.isoformat(),
                    signal.symbol,
                    str(signal.signal_type),
                    regime,
                    signal.score,
                    payload_json,
                ),
            )
            return int(cursor.lastrowid)

    def save_option_candidate(self, candidate: OptionStrategyCandidate) -> int:
        payload_json = _model_to_json(candidate)
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO option_candidates(timestamp, symbol, strategy_name, score, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    candidate.underlying_symbol,
                    candidate.strategy_name,
                    candidate.score,
                    payload_json,
                ),
            )
            return int(cursor.lastrowid)

    def get_recent_signals(
        self, symbol: str | None = None, limit: int = 100
    ) -> list[StoredSignalRecord]:
        if limit <= 0:
            return []

        params: list[Any] = []
        symbol_clause = ""
        if symbol is not None:
            symbol_clause = "WHERE symbol = ?"
            params.append(symbol.strip().upper())
        params.append(limit)

        query = f"""
            SELECT id, timestamp, symbol, 'equity_signal' AS record_type,
                   signal_type AS name, score, payload_json
            FROM signals
            {symbol_clause}
            UNION ALL
            SELECT id, timestamp, symbol, 'option_candidate' AS record_type,
                   strategy_name AS name, score, payload_json
            FROM option_candidates
            {symbol_clause}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        if symbol is not None:
            params = [symbol.strip().upper(), symbol.strip().upper(), limit]

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            StoredSignalRecord(
                id=int(row["id"]),
                timestamp=str(row["timestamp"]),
                symbol=str(row["symbol"]),
                record_type=str(row["record_type"]),
                name=str(row["name"]),
                score=float(row["score"]),
                payload=json.loads(str(row["payload_json"])),
            )
            for row in rows
        ]

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(SIGNALS_TABLE_SQL)
            connection.execute(OPTION_CANDIDATES_TABLE_SQL)
            connection.execute(SIGNALS_INDEX_SQL)
            connection.execute(OPTION_CANDIDATES_INDEX_SQL)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection


def _model_to_json(model: BaseModel) -> str:
    return json.dumps(model.model_dump(mode="json"), sort_keys=True)
