# database

PostgreSQL schema, migrations and seed data.

## How it works

The tables are written as Python classes in `backend/app/models.py`
(SQLAlchemy). **Alembic** turns them into the database:

1. After a change in `models.py`, Alembic compares the classes with the
   database and writes a **migration**: a small numbered file in
   `migrations/versions/` with `upgrade()` (make the change) and `downgrade()`
   (undo it). We read it before using it.
2. The database remembers which migration it is at, in the table
   `alembic_version`.
3. `alembic upgrade head` runs only the migrations that are missing, in order.
   A fresh database gets all of them; an up-to-date one gets none.

The migrations are in git, so every machine gets exactly the same tables.

## Content

| Path | Purpose |
|---|---|
| `alembic.ini` | Alembic settings. The database address is not here, it comes from `.env`. |
| `migrations/env.py` | Connects Alembic to the database and to the table classes. |
| `migrations/versions/` | The migrations, oldest first (file names start with the date). |
| `seed.py` | Planned: demo data (plans, two devices, demo users). |

## Tables

| Table | Holds | Since |
|---|---|---|
| `users` | Customers (identity from BankID, no password). | first migration |
| `face_embeddings` | Encrypted face embeddings. No photos are stored. | first migration |
| `membership_plans` | What can be bought. Prices in whole crowns. | first migration |
| `memberships` | What a user bought and until when it is valid. | first migration |
| `devices` | Cameras at the door, each with a direction (entry / exit). | first migration |
| `access_events` | Every recognition attempt, including denied ones and strangers. | first migration |
| `visits` | One row per stay: entry time and exit time (empty = still inside). | first migration |
| `consents`, `payments`, `entry_codes`, `admins` | Planned, with the steps that use them. | |

The database itself refuses wrong data with `CHECK` rules, for example an
unknown status, a device that is neither entry nor exit, or a membership that
ends before it starts. Every rule has a fixed name such as `ck_users_status`.

Deleting a user removes all personal rows (face, memberships). Visit and event
rows stay but lose the link to the person (`user_id` becomes empty), so
statistics do not change.

## How to run

PostgreSQL must be installed and `.env` filled in first (see
`backend/README.md`). From this `database/` folder, with the project's virtual
environment:

```
python -m alembic upgrade head        # create or update the tables
python -m alembic current             # which migration the database is at
python -m alembic check               # do models.py and the database match?
```

After changing `backend/app/models.py`:

```
python -m alembic revision --autogenerate -m "short description"
```

then read the new file in `migrations/versions/`, and run `upgrade head`.

The tests (`python -m pytest` in `backend/`) bring the separate `facegate_test`
database to the newest migration themselves.
