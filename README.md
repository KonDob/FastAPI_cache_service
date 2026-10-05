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

Work in progress. HTTP endpoints are in place with in-memory stubs; PostgreSQL persistence and real caching come next.

## API behaviour

- `POST /payload` returns `201 Created` with a new id when the input is new, and
  `200 OK` with the **existing** id when the same input was submitted before.
  Repeating a request is therefore safe and never creates duplicates.
- `GET /payload/{id}` returns `{"output": "..."}`, or `404` for an unknown id.
- Both lists must be non-empty and of equal length, otherwise `422`.

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
- **Storage is in-memory for now** (see Status): data is lost on restart and is not shared
  between worker processes.

## Layout

```
├── app/
│   ├── api/           # HTTP routes
│   ├── services/      # payload logic (stubbed for now)
│   └── main.py
├── Test task Python.md
├── pyproject.toml
└── README.md
```

## Run (local)

```bash
uv sync
uv run uvicorn app.main:app --reload
```

API docs: `http://127.0.0.1:8000/docs`
