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

Work in progress. Payloads are persisted in PostgreSQL and identical inputs reuse their id.
The transformer and its per-string cache come next; until then the output is built by a
placeholder.

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
- **No size limits** on list length or string length are enforced yet.
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

Configuration is read from the environment (or `.env`): `DATABASE_URL` is the SQLAlchemy URL.

API docs: `http://127.0.0.1:8000/docs`
