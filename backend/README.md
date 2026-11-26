# backend

The REST API (Python, FastAPI). The only part that talks to the database.

## What it does

- Customer registration and login through BankID (sandbox or built-in mock).
- Membership purchase through a payment gateway (test mode or built-in mock).
- Receives the registration selfie, stores only the encrypted face embedding.
- Answers the door program: whose face is it, is the membership valid, open or deny.
- Records entry and exit events and who is inside.
- Admin API: presence, history, statistics, user management, CSV export.

Done so far: the skeleton with `GET /api/health`.

## Layout

| Path | Purpose |
|---|---|
| `app/main.py` | Creates the FastAPI app and registers the routers. |
| `app/config.py` | Settings loaded from `.env` in the project root. |
| `app/db.py` | Database connection; one session per request. |
| `app/routers/health.py` | `GET /api/health`: is the backend running and can it reach the database? |
| `tests/` | pytest tests. They use the separate `facegate_test` database. |

Planned: `app/models.py` (tables), `app/schemas.py` (request and response
shapes), `app/security.py` (passwords, JWT, device keys, encryption),
`app/services/` (business logic, tested with pytest).

## How it connects to the database

PostgreSQL runs on the same PC as a Windows service. The backend logs in as the
user `facegate`, which owns the databases `facegate` and `facegate_test` but is
not an administrator. The address and password are in `DATABASE_URL` and
`TEST_DATABASE_URL` in `.env` (never committed; names in `.env.example`).

The driver is `pg8000`, written only in Python. The more common `psycopg`
driver ships a compiled file that Windows' Smart App Control blocks.

## How to run

From this `backend/` folder, with the project's virtual environment:

```
pip install -r requirements.txt
python -m pytest                              # tests
python -m uvicorn app.main:app --reload       # start the API
```

Then open http://127.0.0.1:8000/api/health (should say `"database": "ok"`) or
http://127.0.0.1:8000/docs to see and try every endpoint. `--reload` restarts
the server after every code change; stop it with Ctrl+C.

## Setting up PostgreSQL on a new machine

1. Install PostgreSQL 18 with pgAdmin (on Windows: `winget install PostgreSQL.PostgreSQL.18`).
2. Copy `.env.example` to `.env` and fill in new random passwords.
3. As the `postgres` superuser (pgAdmin or `psql`), run:

```sql
CREATE ROLE facegate LOGIN PASSWORD '<the password from DATABASE_URL>';
CREATE DATABASE facegate OWNER facegate;
CREATE DATABASE facegate_test OWNER facegate;
```
