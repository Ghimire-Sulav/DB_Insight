from __future__ import annotations

import re

from insightsql.errors import QueryRejectedError

_BLOCKED_KEYWORDS = {
    "ALTER",
    "ANALYZE",
    "ATTACH",
    "BEGIN",
    "COMMIT",
    "CREATE",
    "DELETE",
    "DETACH",
    "DROP",
    "EXEC",
    "EXECUTE",
    "INSERT",
    "PRAGMA",
    "REINDEX",
    "RELEASE",
    "REPLACE",
    "ROLLBACK",
    "SAVEPOINT",
    "TRUNCATE",
    "UPDATE",
    "VACUUM",
}
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")


def validate_read_only_select(sql: str) -> None:
    """Reject anything except a single SELECT/CTE before SQLite authorizes it."""
    if not isinstance(sql, str) or not sql.strip():
        raise QueryRejectedError("The model returned an empty SQL query.")
    if len(sql) > 10_000:
        raise QueryRejectedError("The generated SQL exceeded the allowed size.")

    tokens = _lex(sql)
    if not tokens:
        raise QueryRejectedError("The model returned an empty SQL query.")
    first_word = next((token for token in tokens if token != ";"), "")
    if first_word.upper() not in {"SELECT", "WITH"}:
        raise QueryRejectedError("Only read-only SELECT queries are allowed.")

    semicolons = [index for index, token in enumerate(tokens) if token == ";"]
    if len(semicolons) > 1 or (
        semicolons and semicolons[0] != len(tokens) - 1
    ):
        raise QueryRejectedError("Only one SQL statement is allowed.")

    for token in tokens:
        if token != ";" and token.upper() in _BLOCKED_KEYWORDS:
            raise QueryRejectedError(
                "Only read-only SELECT queries are allowed; the generated SQL "
                "contains a prohibited operation."
            )


def _lex(sql: str) -> list[str]:
    tokens: list[str] = []
    index = 0
    length = len(sql)

    while index < length:
        char = sql[index]
        if char.isspace():
            index += 1
            continue
        if char == "-" and index + 1 < length and sql[index + 1] == "-":
            newline = sql.find("\n", index + 2)
            index = length if newline == -1 else newline + 1
            continue
        if char == "/" and index + 1 < length and sql[index + 1] == "*":
            end = sql.find("*/", index + 2)
            if end == -1:
                raise QueryRejectedError("The generated SQL contains an unfinished comment.")
            index = end + 2
            continue
        if char == "'":
            index = _skip_quoted(sql, index, "'", "string")
            continue
        if char in {'"', "`"}:
            index = _skip_quoted(sql, index, char, "identifier")
            continue
        if char == "[":
            end = sql.find("]", index + 1)
            if end == -1:
                raise QueryRejectedError(
                    "The generated SQL contains an unfinished quoted identifier."
                )
            index = end + 1
            continue

        match = _WORD.match(sql, index)
        if match:
            tokens.append(match.group(0))
            index = match.end()
            continue
        if char == ";":
            tokens.append(char)
        index += 1

    return tokens


def _skip_quoted(sql: str, start: int, quote: str, kind: str) -> int:
    index = start + 1
    while index < len(sql):
        if sql[index] == quote:
            if index + 1 < len(sql) and sql[index + 1] == quote:
                index += 2
                continue
            return index + 1
        index += 1
    raise QueryRejectedError(f"The generated SQL contains an unfinished {kind}.")
