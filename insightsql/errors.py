class InsightsqlError(Exception):
    """Base class for expected, safe-to-display application errors."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ModelUnavailableError(InsightsqlError):
    def __init__(
        self,
        message: str = (
            "Could not reach Ollama. Install and start Ollama, then download the "
            "configured model (default: qwen2.5-coder:7b)."
        ),
    ) -> None:
        super().__init__(message, status_code=503)


class SqlGenerationError(InsightsqlError):
    def __init__(
        self,
        message: str = (
            "The local model did not return usable SQL. Try rephrasing your question."
        ),
    ) -> None:
        super().__init__(message, status_code=502)


class QueryRejectedError(InsightsqlError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=422)


class DatabaseUnavailableError(InsightsqlError):
    def __init__(
        self,
        message: str = (
            "The employee database is unavailable. Check INSIGHTSQL_DB_PATH."
        ),
    ) -> None:
        super().__init__(message, status_code=503)


class QueryExecutionError(InsightsqlError):
    def __init__(
        self,
        message: str = (
            "The read-only query could not be completed. Check the question and try again."
        ),
        *,
        status_code: int = 400,
    ) -> None:
        super().__init__(message, status_code=status_code)
