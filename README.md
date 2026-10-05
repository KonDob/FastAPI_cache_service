# FastAPI Caching Service

A test assignment: a FastAPI microservice for generating and caching payloads.

## About

This repository holds the solution to a coding task. The service builds a payload from two string lists, runs each string through a “transformer” (simulating an external service), and caches transformation results and payloads in PostgreSQL.

Functionality in brief:

- `POST /payload` — create a payload and return its identifier
- `GET /payload/{id}` — fetch the generated payload
- cache transformer results and reuse ids for payloads that were already generated
- `cache-cli` CLI tool for programmatic API testing
- Docker image for deployment

The full task description is in [`Test task Python.md`](./Test%20task%20Python.md).

## Stack

- Python / FastAPI
- SQLAlchemy
- PostgreSQL
- Docker
- Pydantic Settings (CLI)

## Status

Work in progress. The service is functional: payloads are persisted in PostgreSQL, identical
inputs reuse their id, and transformer results are cached per string. The CLI, tests and the
Docker image come next.

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
- `GET /payload/{id}` returns `{"output": "..."}`, or `404` for an unknown id.
- Both lists must be non-empty and of equal length, otherwise `422`.

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
- **Identical inputs are detected by a hash.** `input_hash` is SHA-256 of the canonical JSON
  `[list_1, list_2]`, with a unique constraint on it. The constraint, not the lookup, is what
  guarantees one id per input when identical requests arrive concurrently.

## Known limitations

- **Output is ambiguous for strings containing `", "`.** The output format is fixed by
  the task as a single comma-joined string, so `["a, b"]` and `["a", "b"]` can produce
  the same text. A JSON array would avoid this but would break the required contract.
- **Payload identity is order- and position-sensitive.** Swapping `list_1` and `list_2`,
  or reordering items, yields a different payload and a different id, because the output
  differs too. Only an exact repeat of the input reuses an id.
- **Input is compared verbatim.** No trimming or case folding is applied, so `"abc"` and
  `"abc "` are different inputs.
- **No size limits** on list length or string length are enforced yet. Very large requests
  (tens of thousands of new strings) would exceed PostgreSQL's bind-parameter limit in a single
  cache insert.
- **The cache never expires.** That is correct for a deterministic transformer; a real external
  service whose results can change would need a TTL or invalidation.
- **PostgreSQL-specific upsert.** `ON CONFLICT DO NOTHING` is used via the PostgreSQL dialect,
  so switching to another database needs that one statement adapted.
- **No migrations.** Tables are created on startup with `create_all`; changing an existing
  column requires recreating the database. Alembic would be the next step for a real deployment.

## Layout

```
├── app/
│   ├── api/           # HTTP routes
│   ├── core/          # settings
│   ├── db/            # engine, session, declarative base
│   ├── models/        # ORM models
│   ├── services/      # payload logic
│   └── main.py
├── docker-compose.yml # local PostgreSQL
├── Test task Python.md
├── pyproject.toml
└── README.md
```

## Run (local)

```bash
uv sync
cp .env.example .env          # adjust DB_PORT / DATABASE_URL if 5432 is taken
docker compose up -d --wait   # PostgreSQL
uv run uvicorn app.main:app --reload
```

Configuration is read from the environment (or `.env`):

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://cache:cache@localhost:5432/cache` | SQLAlchemy database URL |
| `LOG_LEVEL` | `INFO` | Logs show cache hits/misses and every transformer call |

API docs: `http://127.0.0.1:8000/docs`
