# InsightSQL

InsightSQL is a local web application for asking natural-language questions
about the employee-management SQLite database. It uses a local Ollama model to
generate SQL, validates the output, executes only read-only queries, displays
the SQL and results, and stores a bounded history in a separate local file.

## Requirements

- Python 3.11 or newer
- Ollama for Windows, running locally
- The default Ollama model `qwen2.5-coder:7b`, or another model configured with
  `OLLAMA_MODEL`

Install and start Ollama, then download the model:

```powershell
ollama pull qwen2.5-coder:7b
```

## Install and run

From the repository directory:

```powershell
cd "D:\SQL App\DB_Insight"
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

The server binds to loopback only. Do not expose the unauthenticated application
to a network. If PowerShell blocks activation, run the app with the virtual
environment's interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

## Configuration

Settings are read from environment variables; a template is in `.env.example`.
The app does not automatically load `.env` files.

| Variable | Default | Description |
|---|---|---|
| `INSIGHTSQL_DB_PATH` | `employee_management.db` | Path to the existing employee database. The application opens it read-only. |
| `INSIGHTSQL_HISTORY_PATH` | `instance/query_history.sqlite3` | Separate local file for question, SQL, status, and row-count history. |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Local Ollama endpoint. |
| `OLLAMA_MODEL` | `qwen2.5-coder:7b` | Model used for SQL generation. |
| `OLLAMA_TIMEOUT_SECONDS` | `90` | Ollama request timeout (1–600 seconds). |
| `INSIGHTSQL_PORT` | `5000` | Local HTTP port (1–65535). |
| `INSIGHTSQL_HOST` | `127.0.0.1` | Must resolve exclusively to a loopback address. |
| `INSIGHTSQL_SESSION_SECRET` | Random per process | Optional stable Flask session-signing key. If omitted, sessions expire on restart. |
| `INSIGHTSQL_ALLOW_REMOTE_OLLAMA` | `false` | Must be explicitly enabled before a non-loopback model endpoint can be used. This sends schema and questions to that endpoint. |

Relative paths are resolved from the repository root. Set a long, unique
`INSIGHTSQL_SESSION_SECRET` in the process environment for a persistent local
session key. Do not commit credentials or secrets.

## Security model

- The employee database is opened with SQLite `mode=ro` and
  `PRAGMA query_only=ON`.
- The SQL validator accepts one `SELECT` or read-only CTE statement. SQLite's
  authorizer independently denies all writes, DDL, attachment, pragmas,
  unapproved tables, and unapproved functions.
- Query execution is bounded by a two-second SQLite progress timeout, SQLite
  resource limits, a 500-row result cap, and an 850-kilobyte result-data cap
  (leaving room for API metadata within a one-megabyte response).
- Requests require a per-session CSRF token. Browser output is rendered as
  text, not executable HTML. Security headers include a restrictive CSP.
- SQL generation uses Ollama on loopback by default. Remote model endpoints
  are rejected unless explicitly enabled; enabling one transmits the question
  and schema identifiers to that endpoint.
- History is stored in a separate local SQLite file, retains at most 500
  entries for up to 30 days, and does not store result rows.
- This version has no user sign-in or role-based data access. Anyone with
  access to the local machine and browser can query the database, including
  sensitive employee fields. Use only with data appropriate for local,
  authorized access; do not expose it to a shared network.

## Tests

Run the standard-library test suite:

```powershell
py -3 -m unittest discover -s tests -v
```

The application tests use temporary databases and a mocked model response;
they do not require a running Ollama service.
