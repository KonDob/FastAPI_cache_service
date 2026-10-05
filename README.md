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
