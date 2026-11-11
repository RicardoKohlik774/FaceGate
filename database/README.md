# database

PostgreSQL schema, migrations and seed data.

## Planned content

| Path | Purpose |
|---|---|
| `migrations/` | Alembic migration files. Every schema change is one versioned file. |
| `alembic.ini` | Alembic configuration. |
| `seed.py` | Demo data: membership plans, one admin, two devices (entry, exit), demo users. |

## Tables (planned)

| Table | Holds |
|---|---|
| `users` | Customers (identity from BankID). |
| `admins` | Staff accounts. Separate from customers on purpose. |
| `consents` | What each user agreed to, which text version, and when. |
| `face_embeddings` | Encrypted face embeddings. No photos are stored. |
| `membership_plans` | What can be bought. |
| `memberships` | What a user bought and until when it is valid. |
| `payments` | Payment records from the gateway. No card data. |
| `devices` | Cameras at the door, each with a direction (entry / exit). |
| `access_events` | Raw log of every recognition attempt, including denied ones. |
| `visits` | One row per stay: entry time and exit time. |
| `entry_codes` | One-time fallback codes for when the face is not recognised. |

Deleting a user removes all personal rows. Visit, event and payment rows stay
but lose the link to the person, so statistics do not change.

## How to run

Nothing to run yet. Instructions will be added with the first migration.
