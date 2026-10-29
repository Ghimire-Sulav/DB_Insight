from __future__ import annotations

import math
import sqlite3
import time
import json
from pathlib import Path
from typing import Any

from insightsql.errors import (
    DatabaseUnavailableError,
    QueryExecutionError,
    QueryRejectedError,
)

ALLOWED_TABLES = frozenset({"Department", "Employee", "Project", "Employee_Project"})
SAFE_FUNCTIONS = frozenset(
    {
        "abs",
        "avg",
        "coalesce",
        "count",
        "date",
        "datetime",
        "ifnull",
        "julianday",
        "length",
        "lower",
        "max",
        "min",
        "nullif",
        "round",
        "strftime",
        "substr",
        "sum",
        "time",
        "total",
        "trim",
        "upper",
    }
)
MAX_RESULT_ROWS = 500
MAX_RESULT_BYTES = 850_000
MAX_CELL_CHARACTERS = 2_000
MAX_QUERY_SECONDS = 2.0
_LIMITS = (
    ("SQLITE_LIMIT_ATTACHED", 0),
    ("SQLITE_LIMIT_SQL_LENGTH", 10_000),
    ("SQLITE_LIMIT_LENGTH", 2 * 1024 * 1024),
    ("SQLITE_LIMIT_COLUMN", 40),
    ("SQLITE_LIMIT_COMPOUND_SELECT", 10),
    ("SQLITE_LIMIT_EXPR_DEPTH", 50),
    ("SQLITE_LIMIT_VDBE_OP", 100_000),
    ("SQLITE_LIMIT_FUNCTION_ARG", 20),
    ("SQLITE_LIMIT_LIKE_PATTERN_LENGTH", 1_000),
    ("SQLITE_LIMIT_VARIABLE_NUMBER", 100),
)


def _connect_readonly(database_path: Path) -> sqlite3.Connection:
    try:
        resolved = database_path.expanduser().resolve(strict=True)
        if not resolved.is_file():
            raise FileNotFoundError
        connection = sqlite3.connect(
            f"{resolved.as_uri()}?mode=ro",
            uri=True,
            timeout=1.5,
            isolation_level=None,
        )
    except (OSError, sqlite3.Error, ValueError) as error:
        raise DatabaseUnavailableError() from error

    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA trusted_schema = OFF")
        for limit_name, limit_value in _LIMITS:
            limit_code = getattr(sqlite3, limit_name, None)
            if limit_code is not None:
                connection.setlimit(limit_code, limit_value)
        return connection
    except sqlite3.Error as error:
        connection.close()
        raise DatabaseUnavailableError() from error


def get_schema_description(database_path: Path) -> str:
    connection = _connect_readonly(database_path)
    try:
        tables = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        existing = {row["name"] for row in tables}
        missing = ALLOWED_TABLES - existing
        if missing:
            raise DatabaseUnavailableError(
                "The employee database is missing required tables. Check that the "
                "configured database matches this project's schema."
            )

        lines: list[str] = []
        for table_name in sorted(ALLOWED_TABLES):
            escaped_name = table_name.replace('"', '""')
            columns = connection.execute(
                f'PRAGMA table_info("{escaped_name}")'
            ).fetchall()
            column_names = [row["name"] for row in columns]
            lines.append(f"{table_name}({', '.join(column_names)})")
        return "\n".join(lines)
    except sqlite3.Error as error:
        raise DatabaseUnavailableError() from error
    finally:
        connection.close()


def execute_read_query(database_path: Path, sql: str) -> dict[str, Any]:
    try:
        connection = _connect_readonly(database_path)
    except DatabaseUnavailableError:
        raise

    started = time.monotonic()
    deadline = started + MAX_QUERY_SECONDS
    try:
        connection.set_authorizer(_authorize)
        connection.set_progress_handler(
            lambda: 1 if time.monotonic() > deadline else 0,
            1_000,
        )
        cursor = connection.execute(sql)
        if cursor.description is None:
            raise QueryRejectedError("Only SELECT queries that return rows are allowed.")
        columns = [
            str(column[0])[:MAX_CELL_CHARACTERS] for column in cursor.description
        ]
        rows: list[list[Any]] = []
        result_bytes = 0
        truncated = False
        for row_index in range(MAX_RESULT_ROWS + 1):
            row = cursor.fetchone()
            if row is None:
                break
            if row_index == MAX_RESULT_ROWS:
                truncated = True
                break
            normalized = [_json_value(value) for value in row]
            row_bytes = len(
                json.dumps(normalized, ensure_ascii=False, separators=(",", ":")).encode(
                    "utf-8"
                )
            )
            if result_bytes + row_bytes > MAX_RESULT_BYTES:
                truncated = True
                break
            rows.append(normalized)
            result_bytes += row_bytes
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
        }
    except QueryRejectedError:
        raise
    except sqlite3.DatabaseError as error:
        if time.monotonic() > deadline or "interrupted" in str(error).lower():
            raise QueryExecutionError(
                "The query took too long. Try a more specific question.",
                status_code=408,
            ) from error
        error_text = str(error).lower()
        if (
            "not authorized" in error_text
            or "prohibited" in error_text
            or "no such function" in error_text
        ):
            raise QueryRejectedError(
                "The query was rejected by the read-only SQL safety policy."
            ) from error
        raise QueryExecutionError() from error
    finally:
        connection.close()


def _authorize(
    action: int,
    argument_one: str | None,
    argument_two: str | None,
    database_name: str | None,
    trigger_name: str | None,
) -> int:
    del database_name, trigger_name
    if action in {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_RECURSIVE,
    }:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ:
        if argument_one in ALLOWED_TABLES:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION:
        function_name = (argument_two or argument_one or "").lower()
        if function_name in SAFE_FUNCTIONS:
            return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def _json_value(value: Any) -> Any:
    if isinstance(value, bytes):
        content = value[:MAX_CELL_CHARACTERS // 2].hex()
        return content + ("… [truncated]" if len(value) > MAX_CELL_CHARACTERS // 2 else "")
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, str) and len(value) > MAX_CELL_CHARACTERS:
        return value[:MAX_CELL_CHARACTERS] + "… [truncated]"
    return value
