from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent


def _boolean(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_path: Path
    history_path: Path
    ollama_base_url: str
    ollama_model: str
    ollama_timeout_seconds: float
    allow_remote_ollama: bool

    @classmethod
    def from_environment(cls) -> "Settings":
        timeout_value = os.environ.get("OLLAMA_TIMEOUT_SECONDS", "90")
        try:
            timeout = float(timeout_value)
        except ValueError as error:
            raise RuntimeError("OLLAMA_TIMEOUT_SECONDS must be a number.") from error
        if not 1 <= timeout <= 600:
            raise RuntimeError("OLLAMA_TIMEOUT_SECONDS must be between 1 and 600.")

        return cls(
            database_path=_resolve_path(
                os.environ.get("INSIGHTSQL_DB_PATH", "employee_management.db")
            ),
            history_path=_resolve_path(
                os.environ.get(
                    "INSIGHTSQL_HISTORY_PATH", "instance/query_history.sqlite3"
                )
            ),
            ollama_base_url=os.environ.get(
                "OLLAMA_BASE_URL", "http://127.0.0.1:11434"
            ).rstrip("/"),
            ollama_model=os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b").strip(),
            ollama_timeout_seconds=timeout,
            allow_remote_ollama=_boolean("INSIGHTSQL_ALLOW_REMOTE_OLLAMA"),
        )


def _resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = APP_ROOT / path
    return path.resolve()
