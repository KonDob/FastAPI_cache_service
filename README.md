# FastAPI Caching Service

A test assignment: a FastAPI microservice for generating and caching payloads.

## About

This repository holds the solution to a coding task. The service builds a payload from two
string lists, runs each string through a "transformer" (simulating an external service), and
caches transformation results and payloads in PostgreSQL.

Functionality in brief:

- `POST /payload` — create a payload and return its identifier
- `GET /payload/{id}` — fetch the generated payload
- cache transformer results and reuse ids for payloads that were already generated
- `cache-cli` CLI tool for programmatic API testing
- Docker image for deployment

The full task description is in [`Test task Python.md`](./Test%20task%20Python.md).

## Stack

- Python 3.11+ / FastAPI, served by uvicorn
- SQLAlchemy 2 with psycopg 3, PostgreSQL 17
- Pydantic Settings and httpx2 (CLI)
- Docker and docker compose
- uv for dependencies; pytest, ruff and mypy (strict) for checks

## Status

Feature complete. The service and the `cache-cli` client are functional, covered by tests and
run in Docker: payloads are persisted in PostgreSQL, identical inputs reuse their id, and
transformer results are cached per string.

## Clarifications

Questions raised on the task and the answers received from the reviewers:

- **"Payload files"** — payloads are stored in the database; no files are generated.
- **CLI `-h` clash** — `-H` / `--host` selects the server, `-h` / `--help` shows help.
- **Payload identity** — an exact match of `list_1` and `list_2`, element order included.
  The transformer is cached per string, so a new payload built from already known strings
  gets its own id but reuses the cached transformations.

## API behaviour

- `POST /payload` returns `201 Created` with a new id when the input is new, and
  `200 OK` with the **existing** id when the same input was submitted before.
  Repeating a request is therefore safe and never creates duplicates.
- `POST /payload` returns `502 Bad Gateway` when the transformer service fails or returns a
  malformed answer; nothing is cached or stored in that case.
- `GET /payload/{id}` returns `{"output": "..."}`, or `404` for an unknown id.
- Both lists must be non-empty and of equal length, hold at most 1000 items each, and every
  string must be at most 1000 characters long and free of NUL characters; otherwise `422`.
  Only the equal length comes from the task; the other bounds are ours (see Design decisions).
- Validation errors use FastAPI's standard `422` body, with non-ASCII characters escaped
  (`\u0436` instead of `ж`); any JSON parser reads it back to the same value.
- `GET /health` returns `{"status": "ok"}`, or `503` when the database is unreachable; the
  Docker healthcheck uses it.

## Design decisions

- **Payloads are stored ready-made.** The final `output` string is built once on `POST` and
  saved in the `payload` table. A payload never changes, so `GET` is a single primary-key
  lookup and never rebuilds the string or touches the transformer.
- **The transformer is a simulated external service.** It upper-cases strings behind a batch
  interface (`list[str] -> list[str]`), logs every call, and is injected as a
  FastAPI dependency so tests can replace it with a counting fake.
- **Transformer results are cached per string** in the `transform_cache` table. On `POST` the
  service looks up all strings of the request at once and calls the transformer **once**, only
  with the strings that are not cached yet; a string repeated within a request is sent once.
  New results are committed before the payload is stored, so they are kept even if storing the
  payload fails.
- **Cache rows are keyed by the SHA-256 of the string**, not the string itself: a B-tree index on
  unbounded text fails for long values, a fixed-size digest does not. Concurrent requests that
  cache the same string do not conflict (`INSERT ... ON CONFLICT DO NOTHING`).
- **Input size is bounded by our choice, not by the task.** The task only requires the two
  lists to have the same length; the three-item sample is an illustration, not a limit. We
  added the bounds (1–1000 items per list, up to 1000 characters per string) so that a single
  request cannot overload the transformer or the database: all new strings of a request are
  cached in one `INSERT`, and PostgreSQL caps the number of parameters per statement. The
  values are constants in `app/api/routes.py` and can be tuned freely.
- **Validation errors are rendered as ASCII-only JSON.** A `422` body echoes the rejected
  input, and JSON may carry strings that cannot be encoded as UTF-8 at all (a lone surrogate
  such as `"\ud800"`). FastAPI's default handler then crashes with a `500` while reporting the
  error. Our handler (`app/api/errors.py`) returns the same body with non-ASCII characters
  escaped, so such input gets a proper `422`. Strings with NUL characters are rejected for a
  similar reason: PostgreSQL `text` cannot store them.
- **Identical inputs are detected by a hash.** `input_hash` is SHA-256 of the canonical JSON
  `[list_1, list_2]`, with a unique constraint on it. The constraint, not the lookup, is what
  guarantees one id per input when identical requests arrive concurrently.

## Known limitations

- **Output is ambiguous for strings containing `", "`.** The output format is fixed by
  the task as a single comma-joined string, so `["a, b"]` and `["a", "b"]` can produce
  the same text. A JSON array would avoid this but would break the required contract.
- **Input is compared verbatim.** No trimming or case folding is applied, so `"abc"` and
  `"abc "` are different inputs.
- **Concurrent requests with the same new strings each call the transformer.** Both miss the
  cache before either has stored its results, so the service is called twice. The result is
  still correct and only one copy is cached; avoiding the extra call would need a per-string
  lock, which is not worth the complexity here.
- **The cache never expires.** That is correct for a deterministic transformer; a real external
  service whose results can change would need a TTL or invalidation.
- **PostgreSQL-specific upsert.** `ON CONFLICT DO NOTHING` is used via the PostgreSQL dialect,
  so switching to another database needs that one statement adapted.
- **No migrations.** Tables are created on startup with `create_all`; changing an existing
  column requires recreating the database. Alembic would be the next step for a real deployment.
- **Credentials are for local use only.** The database user and password in
  `docker-compose.yml` are fixed development values; a real deployment would inject them as
  secrets.
- **CLI help shows types instead of names.** `cache-cli --help` prints `str` or `AnyHttpUrl`
  where the task writes `FILE|-` or `URL`; Pydantic Settings offers no simple way to rename
  them, so each option's meaning is in its description.

## Layout

```
├── app/
│   ├── api/           # HTTP routes
│   ├── core/          # settings
│   ├── db/            # engine, session, declarative base
│   ├── models/        # ORM models
│   ├── services/      # payload logic
│   └── main.py
├── cache_cli/         # cache-cli: HTTP client, independent of app/
├── tests/
│   ├── unit/          # pure helpers and CLI arguments, no database
│   └── integration/   # API, service and CLI against real PostgreSQL
├── Dockerfile         # service image
├── docker-compose.yml # service + PostgreSQL
├── Test task Python.md
├── pyproject.toml
└── README.md
```

## Run with Docker

```bash
docker compose up -d --build --wait   # service on http://localhost:8000 + PostgreSQL
curl http://localhost:8000/health
docker compose exec app cache-cli -j '{"list_1": ["a"], "list_2": ["b"]}'
docker compose down                   # add -v to also drop the database volume
```

`APP_PORT` and `DB_PORT` change the published ports (defaults `8000` and `5432`). The image is
built in two stages with `uv` from the lock file; the runtime stage contains only the virtualenv
(no sources, no dev tools) and runs as an unprivileged user. `cache-cli` is installed in the
image too.

## Run (local development)

```bash
uv sync
cp .env.example .env               # adjust DB_PORT / DATABASE_URL if 5432 is taken
docker compose up -d --wait db     # PostgreSQL only
uv run uvicorn app.main:app --reload
```

Configuration is read from the environment (or `.env`):

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://cache:cache@localhost:5432/cache` | SQLAlchemy database URL |
| `LOG_LEVEL` | `INFO` | Logs show cache hits/misses and every transformer call |

API docs: `http://127.0.0.1:8000/docs`

## CLI

`cache-cli` is installed with the project (`uv sync`) and talks to a running service over HTTP:

```
cache-cli [-H|--host URL] [-r|--repeat N] [-i|--input FILE|-] [-j|--json JSON] [-o|--output FILE|-] [-h|--help]
```

| Option | Default | Meaning |
|---|---|---|
| `-H`, `--host` | `http://localhost:8000` | Base URL of the service (`http` or `https`) |
| `-r`, `--repeat` | `1` | How many times the same request is sent (at least 1) |
| `-i`, `--input` | | File with the request JSON; `-` reads stdin |
| `-j`, `--json` | | Request JSON given inline |
| `-o`, `--output` | `-` | File to write results to; `-` writes to stdout |

The request JSON is the body of `POST /payload`; exactly one of `--input` and `--json` is required.
Each iteration creates the payload and reads it back. Results are printed as a JSON array:

```bash
$ cache-cli -j '{"list_1": ["first string"], "list_2": ["other string"]}' -r 2
[
  {"iteration": 1, "id": "3753…", "status": "created",  "output": "FIRST STRING, OTHER STRING", "elapsed_ms": 42.4},
  {"iteration": 2, "id": "3753…", "status": "existing", "output": "FIRST STRING, OTHER STRING", "elapsed_ms": 7.3}
]
```

`status` is `created` when the service generated a new payload and `existing` when it reused the
identifier of an earlier identical request. Exit codes: `0` success, `1` the service failed or
rejected the request (message on stderr, nothing on stdout), `2` invalid arguments or input.

Design notes:

- **Arguments are parsed and sanitized by Pydantic Settings** (`cache_cli/settings.py`): the URL
  scheme, `--repeat >= 1`, that the input file exists and that the request JSON has two lists of
  strings of equal length are checked before any request is sent. The service's own size limits
  are not duplicated in the client; a request breaking them is reported as the server's `422`.
- **Only the command line is read.** Environment variables and `.env` are ignored, so a stray
  variable such as `host` cannot change what the tool does.
- **The client does not import `app/`.** It is a plain HTTP client of the API and works against
  any running instance. Tests drive it through `TestClient`, so no real server is needed.
- **`-H` instead of `-h` for the host**, as agreed (see Clarifications).
- **`--repeat` sends the same request N times**, which shows the identifier being reused and the
  faster cached responses; it runs sequentially and stops at the first failure.

## Tests and checks

```bash
docker compose up -d --wait db   # integration tests need PostgreSQL
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy app cache_cli tests
```

Integration tests use a separate `cache_test` database on the same server as `DATABASE_URL`
(created automatically and reset before every test), so development data is never touched.
Set `TEST_DATABASE_URL` to point them elsewhere. They run against PostgreSQL rather than
SQLite on purpose: the service relies on PostgreSQL behaviour (`ON CONFLICT`, unique
constraints under concurrency). The transformer is replaced by a fake that records its calls,
which is how the tests prove that cached strings are never sent to it again. Race conditions
are reproduced deterministically by running a competing request from inside the transformer
call, instead of relying on thread timing.

Tests must run sequentially: they share the `cache_test` database and truncate it before
each test, so parallel runners such as `pytest -n` (pytest-xdist) are not supported.
