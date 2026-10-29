from __future__ import annotations

import logging
import os
import secrets
import sqlite3
from pathlib import Path
from typing import Any

from flask import Flask, abort, current_app, g, jsonify, render_template, request, session
from werkzeug.exceptions import HTTPException

from insightsql.config import Settings
from insightsql.database import (
    DatabaseUnavailableError,
    execute_read_query,
    get_schema_description,
)
from insightsql.errors import (
    ModelUnavailableError,
    QueryExecutionError,
    QueryRejectedError,
    SqlGenerationError,
)
from insightsql.history import HistoryStore
from insightsql.ollama import generate_sql
from insightsql.security import validate_read_only_select

MAX_QUESTION_LENGTH = 1000
MAX_SQL_LENGTH = 10_000


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=str(app_root / "templates"),
        static_folder=str(app_root / "static"),
    )
    settings = Settings.from_environment()
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("INSIGHTSQL_SESSION_SECRET") or secrets.token_hex(32),
        DATABASE_PATH=settings.database_path,
        HISTORY_PATH=settings.history_path,
        OLLAMA_BASE_URL=settings.ollama_base_url,
        OLLAMA_MODEL=settings.ollama_model,
        OLLAMA_TIMEOUT_SECONDS=settings.ollama_timeout_seconds,
        ALLOW_REMOTE_OLLAMA=settings.allow_remote_ollama,
        MAX_CONTENT_LENGTH=16 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=False,
        JSON_SORT_KEYS=False,
    )
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("INSIGHTSQL_SESSION_SECRET must not be empty.")

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.extensions["insightsql_history"] = HistoryStore(
        Path(app.config["HISTORY_PATH"])
    )

    if not app.logger.handlers:
        logging.basicConfig(level=logging.INFO)

    @app.before_request
    def assign_request_id() -> None:
        g.request_id = secrets.token_hex(16)

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "base-uri 'none'; "
            "form-action 'self'; "
            "frame-ancestors 'none'"
        )
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        return response

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        if request.path.startswith("/api/"):
            return jsonify(
                error={
                    "message": error.description,
                    "request_id": getattr(g, "request_id", ""),
                }
            ), error.code
        return error

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        app.logger.error(
            "Unhandled request failure (request_id=%s)",
            getattr(g, "request_id", ""),
            exc_info=error,
        )
        if request.path.startswith("/api/"):
            return jsonify(
                error={
                    "message": "An unexpected error occurred. Please try again.",
                    "request_id": getattr(g, "request_id", ""),
                }
            ), 500
        return "An unexpected error occurred. Please try again.", 500

    @app.get("/")
    def index():
        csrf_token = session.get("csrf_token")
        if not csrf_token:
            csrf_token = secrets.token_urlsafe(32)
            session["csrf_token"] = csrf_token
        return render_template("index.html", csrf_token=csrf_token)

    @app.get("/api/history")
    def history():
        store: HistoryStore = app.extensions["insightsql_history"]
        return jsonify({"items": store.latest(limit=50)})

    @app.post("/api/query")
    def query():
        _validate_csrf()
        payload = request.get_json()
        if not isinstance(payload, dict) or set(payload) != {"question"}:
            return _json_error("Send a JSON object containing only 'question'.", 400)
        question = payload["question"]
        if not isinstance(question, str):
            return _json_error("Enter a question using plain text.", 400)
        question = question.strip()
        if not question or len(question) > MAX_QUESTION_LENGTH:
            return _json_error(
                f"Enter a question between 1 and {MAX_QUESTION_LENGTH} characters.",
                400,
            )

        generated_sql = ""
        try:
            schema = get_schema_description(Path(app.config["DATABASE_PATH"]))
            generated_sql = generate_sql(
                question=question,
                schema=schema,
                base_url=app.config["OLLAMA_BASE_URL"],
                model=app.config["OLLAMA_MODEL"],
                timeout_seconds=app.config["OLLAMA_TIMEOUT_SECONDS"],
                allow_remote=app.config["ALLOW_REMOTE_OLLAMA"],
            )
            if len(generated_sql) > MAX_SQL_LENGTH:
                raise QueryRejectedError("The generated SQL exceeded the allowed size.")
            validate_read_only_select(generated_sql)
            result = execute_read_query(
                Path(app.config["DATABASE_PATH"]), generated_sql
            )
        except ModelUnavailableError as error:
            _record_query(question, generated_sql, "error", None, error.message)
            return _json_error(error.message, 503)
        except SqlGenerationError as error:
            _record_query(question, generated_sql, "error", None, error.message)
            return _json_error(error.message, 502)
        except QueryRejectedError as error:
            _record_query(question, generated_sql, "rejected", None, error.message)
            return _json_error(
                error.message,
                422,
                sql=generated_sql,
            )
        except DatabaseUnavailableError as error:
            _record_query(question, generated_sql, "error", None, error.message)
            return _json_error(error.message, 503)
        except QueryExecutionError as error:
            _record_query(question, generated_sql, "error", None, error.message)
            return _json_error(
                error.message,
                error.status_code,
                sql=generated_sql,
            )

        history_id = _record_query(
            question,
            generated_sql,
            "success",
            result["row_count"],
            None,
        )
        response = {
            "question": question,
            "sql": generated_sql,
            "columns": result["columns"],
            "rows": result["rows"],
            "row_count": result["row_count"],
            "truncated": result["truncated"],
            "history_id": history_id,
            "request_id": g.request_id,
        }
        if history_id is None:
            response["warning"] = (
                "The query succeeded, but query history could not be saved."
            )
        return jsonify(response)

    return app


def _validate_csrf() -> None:
    expected = session.get("csrf_token", "")
    supplied = request.headers.get("X-CSRF-Token", "")
    if not expected or not secrets.compare_digest(expected, supplied):
        abort(
            400,
            description="Your session token expired. Refresh the page and try again.",
        )
    origin = request.headers.get("Origin")
    if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
        abort(403, description="The request origin was rejected.")


def _json_error(message: str, status_code: int, **extra: Any):
    return jsonify(
        {
            "error": {"message": message, "request_id": g.request_id},
            **extra,
        }
    ), status_code


def _record_query(
    question: str,
    sql: str,
    status: str,
    row_count: int | None,
    error_message: str | None,
) -> int | None:
    store: HistoryStore = current_app.extensions["insightsql_history"]
    try:
        return store.record(
            question=question,
            sql=sql,
            status=status,
            row_count=row_count,
            error_message=error_message,
        )
    except sqlite3.Error:
        current_app.logger.exception(
            "Could not persist query history (request_id=%s)",
            getattr(g, "request_id", ""),
        )
        return None
