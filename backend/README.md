# backend

The REST API (Python, FastAPI). The only part that talks to the database.

## What it does

- Customer registration and login through BankID (sandbox or built-in mock).
- Membership purchase through a payment gateway (test mode or built-in mock).
- Receives the registration selfie, stores only the encrypted face embedding.
- Answers the door program: whose face is it, is the membership valid, open or deny.
- Records entry and exit events and who is inside.
- Admin API: presence, history, statistics, user management, CSV export.

## Planned layout

| Path | Purpose |
|---|---|
| `app/main.py` | Creates the FastAPI app and registers the routers. |
| `app/config.py` | Settings loaded from `.env`. |
| `app/db.py` | Database connection. |
| `app/models.py` | Database tables (SQLAlchemy). |
| `app/schemas.py` | Request and response shapes (Pydantic). |
| `app/security.py` | Password hashing, JWT, device keys, encryption. |
| `app/routers/` | HTTP endpoints. No business logic here. |
| `app/services/` | Business logic. Tested with pytest. |
| `tests/` | pytest tests. |

## How to run

Nothing to run yet. Instructions will be added with the first code.
