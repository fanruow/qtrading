"""SQLite schema definitions for signal persistence."""

SIGNALS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    regime TEXT,
    score REAL NOT NULL,
    payload_json TEXT NOT NULL
)
"""

OPTION_CANDIDATES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS option_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    score REAL NOT NULL,
    payload_json TEXT NOT NULL
)
"""

SIGNALS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_signals_symbol_timestamp
ON signals(symbol, timestamp DESC)
"""

OPTION_CANDIDATES_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_option_candidates_symbol_timestamp
ON option_candidates(symbol, timestamp DESC)
"""
