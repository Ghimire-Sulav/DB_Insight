from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from insightsql import create_app
from insightsql.errors import ModelUnavailableError, SqlGenerationError

ROOT = Path(__file__).resolve().parents[1]


class ApplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        directory = Path(self.temp.name)
        self.database_path = directory / "employee_management.db"
        connection = sqlite3.connect(self.database_path)
        try:
            connection.executescript(
                (ROOT / "employee_management.sql").read_text(encoding="utf-8")
            )
        finally:
            connection.close()
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "DATABASE_PATH": self.database_path,
                "HISTORY_PATH": directory / "query_history.sqlite3",
                "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
                "OLLAMA_MODEL": "test-model",
                "OLLAMA_TIMEOUT_SECONDS": 2,
                "ALLOW_REMOTE_OLLAMA": False,
            }
        )
        self.client = self.app.test_client()
        response = self.client.get("/")
        self.csrf_token = response.get_data(as_text=True).split(
            '<meta name="csrf-token" content="', 1
        )[1].split('"', 1)[0]

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_query_generates_validates_and_executes_select(self) -> None:
        with patch(
            "insightsql.generate_sql",
            return_value=(
                "SELECT first_name, last_name FROM Employee "
                "WHERE department_id = 1 ORDER BY employee_id"
            ),
        ):
            response = self._query("Show Engineering employees")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["row_count"], 4)
        self.assertEqual(payload["rows"][0], ["Aarav", "Sharma"])
        self.assertIn("SELECT", payload["sql"])
        history = self.client.get("/api/history").get_json()["items"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "success")

    def test_generated_destructive_query_is_rejected_without_database_changes(self) -> None:
        before = self.database_path.read_bytes()
        with patch("insightsql.generate_sql", return_value="DELETE FROM Employee"):
            response = self._query("Remove employees")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.database_path.read_bytes(), before)
        self.assertEqual(
            self.client.get("/api/history").get_json()["items"][0]["status"],
            "rejected",
        )

    def test_csrf_token_is_required(self) -> None:
        response = self.client.post(
            "/api/query",
            json={"question": "List employees"},
        )
        self.assertEqual(response.status_code, 400)

    def test_bad_question_does_not_call_model(self) -> None:
        with patch("insightsql.generate_sql") as generator:
            response = self._query(" ")
        self.assertEqual(response.status_code, 400)
        generator.assert_not_called()

    def test_model_and_database_errors_are_friendly(self) -> None:
        cases = (
            (ModelUnavailableError("Ollama is unavailable."), 503),
            (SqlGenerationError("Could not generate SQL."), 502),
        )
        for error, status in cases:
            with self.subTest(status=status), patch(
                "insightsql.generate_sql", side_effect=error
            ):
                response = self._query("List employees")
            self.assertEqual(response.status_code, status)
            self.assertIn("message", response.get_json()["error"])
            self.assertNotIn("Traceback", response.get_data(as_text=True))

    def test_security_headers_are_present(self) -> None:
        response = self.client.get("/")
        self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def _query(self, question: str):
        return self.client.post(
            "/api/query",
            json={"question": question},
            headers={"X-CSRF-Token": self.csrf_token},
        )


if __name__ == "__main__":
    unittest.main()
