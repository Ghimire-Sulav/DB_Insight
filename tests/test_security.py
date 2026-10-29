from __future__ import annotations

import sqlite3
import json
import tempfile
import unittest
from pathlib import Path

from insightsql.database import execute_read_query
from insightsql.errors import QueryRejectedError
from insightsql.security import validate_read_only_select

ROOT = Path(__file__).resolve().parents[1]


class SqlValidationTests(unittest.TestCase):
    def test_allows_select_and_read_only_cte(self) -> None:
        validate_read_only_select("SELECT first_name FROM Employee;")
        validate_read_only_select(
            "WITH staff AS (SELECT first_name FROM Employee) SELECT * FROM staff"
        )

    def test_allows_banned_words_inside_string_literals_and_comments(self) -> None:
        validate_read_only_select(
            "SELECT 'DROP TABLE' AS note FROM Employee -- DELETE rows\n"
        )

    def test_rejects_non_select_statements(self) -> None:
        for sql in (
            "DELETE FROM Employee",
            "UPDATE Employee SET salary = 0",
            "INSERT INTO Employee VALUES (1)",
            "DROP TABLE Employee",
            "ALTER TABLE Employee ADD COLUMN x",
            "TRUNCATE Employee",
            "PRAGMA table_info(Employee)",
        ):
            with self.subTest(sql=sql), self.assertRaises(QueryRejectedError):
                validate_read_only_select(sql)

    def test_rejects_chained_statements_and_prohibited_cte_operations(self) -> None:
        for sql in (
            "SELECT 1; DROP TABLE Employee",
            "SELECT 1; SELECT 2",
            "WITH changed AS (DELETE FROM Employee RETURNING *) SELECT * FROM changed",
        ):
            with self.subTest(sql=sql), self.assertRaises(QueryRejectedError):
                validate_read_only_select(sql)

    def test_rejects_unterminated_quotes_and_comments(self) -> None:
        for sql in ("SELECT 'unterminated", "SELECT 1 /* unfinished"):
            with self.subTest(sql=sql), self.assertRaises(QueryRejectedError):
                validate_read_only_select(sql)


class ReadOnlyExecutionTests(unittest.TestCase):
    def test_executes_select_and_returns_capped_rows(self) -> None:
        result = execute_read_query(
            ROOT / "employee_management.db",
            "SELECT first_name, last_name FROM Employee ORDER BY employee_id",
        )
        self.assertEqual(result["columns"], ["first_name", "last_name"])
        self.assertEqual(result["row_count"], 20)
        self.assertFalse(result["truncated"])

    def test_authorizer_blocks_unapproved_functions_and_tables(self) -> None:
        cases = (
            "SELECT load_extension('extension')",
            "SELECT name FROM sqlite_master",
            "SELECT writefile('file', 'content')",
        )
        for sql in cases:
            with self.subTest(sql=sql), self.assertRaises(QueryRejectedError):
                execute_read_query(ROOT / "employee_management.db", sql)

    def test_database_file_cannot_be_modified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.sqlite3"
            connection = sqlite3.connect(path)
            try:
                with connection:
                    connection.execute(
                        "CREATE TABLE Employee (employee_id INTEGER, first_name TEXT)"
                    )
                    connection.execute(
                        "INSERT INTO Employee VALUES (1, 'Test')"
                    )
            finally:
                connection.close()
            original_bytes = path.read_bytes()
            with self.assertRaises(QueryRejectedError):
                execute_read_query(path, "DELETE FROM Employee")
            result = execute_read_query(path, "SELECT first_name FROM Employee")
            self.assertEqual(result["rows"], [["Test"]])
            self.assertEqual(path.read_bytes(), original_bytes)

    def test_result_rows_and_serialized_data_are_capped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.sqlite3"
            connection = sqlite3.connect(path)
            try:
                with connection:
                    connection.execute(
                        "CREATE TABLE Employee (employee_id INTEGER, first_name TEXT)"
                    )
                    connection.executemany(
                        "INSERT INTO Employee VALUES (?, ?)",
                        [(index, "x" * 3000) for index in range(501)],
                    )
            finally:
                connection.close()

            result = execute_read_query(path, "SELECT first_name FROM Employee")
            serialized_size = len(
                json.dumps(
                    {"columns": result["columns"], "rows": result["rows"]},
                    ensure_ascii=False,
                ).encode("utf-8")
            )
            self.assertTrue(result["truncated"])
            self.assertLessEqual(result["row_count"], 500)
            self.assertLessEqual(serialized_size, 1_000_000)


if __name__ == "__main__":
    unittest.main()
