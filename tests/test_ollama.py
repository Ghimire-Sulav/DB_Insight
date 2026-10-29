from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from insightsql.errors import ModelUnavailableError
from insightsql.ollama import generate_sql


class OllamaClientTests(unittest.TestCase):
    def test_remote_endpoint_is_rejected_by_default(self) -> None:
        with patch("insightsql.ollama.urlopen") as urlopen:
            with self.assertRaises(ModelUnavailableError):
                generate_sql(
                    question="List employees",
                    schema="Employee(employee_id)",
                    base_url="https://example.invalid",
                    model="test-model",
                    timeout_seconds=1,
                )
        urlopen.assert_not_called()

    def test_model_response_is_parsed_as_sql_json(self) -> None:
        generated_sql = "SELECT employee_id FROM Employee"
        body = json.dumps(
            {"response": json.dumps({"sql": generated_sql})}
        ).encode("utf-8")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self, _limit):
                return body

        with patch("insightsql.ollama.urlopen", return_value=FakeResponse()) as urlopen:
            result = generate_sql(
                question="List employee IDs",
                schema="Employee(employee_id)",
                base_url="http://127.0.0.1:11434",
                model="test-model",
                timeout_seconds=1,
            )

        self.assertEqual(result, generated_sql)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/generate")
        self.assertEqual(json.loads(request.data)["model"], "test-model")


if __name__ == "__main__":
    unittest.main()
