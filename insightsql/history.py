from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Iterator

HISTORY_LIMIT = 500
RETENTION_DAYS = 30


class HistoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS query_history (
                    id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    question TEXT NOT NULL,
                    sql TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('success', 'error', 'rejected')),
                    row_count INTEGER,
                    error_message TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_query_history_created_at "
                "ON query_history(created_at DESC)"
            )
            self._prune(connection)

    def record(
        self,
        *,
        question: str,
        sql: str,
        status: str,
        row_count: int | None,
        error_message: str | None,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO query_history
                    (created_at, question, sql, status, row_count, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    question[:1000],
                    sql[:10_000],
                    status,
                    row_count,
                    error_message[:500] if error_message else None,
                ),
            )
            self._prune(connection)
            return int(cursor.lastrowid)

    def latest(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, created_at, question, sql, status, row_count, error_message
                FROM query_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (min(max(limit, 1), HISTORY_LIMIT),),
            ).fetchall()
        return [dict(row) for row in rows]

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=2.0)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _prune(connection: sqlite3.Connection) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat(
            timespec="seconds"
        )
        connection.execute("DELETE FROM query_history WHERE created_at < ?", (cutoff,))
        connection.execute(
            """
            DELETE FROM query_history
            WHERE id NOT IN (
                SELECT id FROM query_history ORDER BY id DESC LIMIT ?
            )
            """,
            (HISTORY_LIMIT,),
        )
