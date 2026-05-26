from __future__ import annotations

from src.utils.env import load_dotenv


def test_load_dotenv_sets_alpaca_env(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "ALPACA_API_KEY=key_from_file",
                "ALPACA_SECRET_KEY=secret_from_file",
                "ALPACA_DATA_FEED=iex",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.delenv("ALPACA_DATA_FEED", raising=False)

    load_dotenv(env_file)

    assert __import__("os").environ["ALPACA_API_KEY"] == "key_from_file"
    assert __import__("os").environ["ALPACA_SECRET_KEY"] == "secret_from_file"
    assert __import__("os").environ["ALPACA_DATA_FEED"] == "iex"
