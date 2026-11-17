# FaceGate

Self-service entry system for small facilities (gyms, coworking spaces, clubs).
A customer registers and pays online, takes a selfie, and from then on a camera
at the door recognises their face, checks the membership and opens the door.

School project, SPŠE Ječná, Prague.

## Parts

| Folder | What it is | Technology |
|---|---|---|
| [`recognition/`](recognition/README.md) | Door program: camera, face recognition, liveness, door relay | Python, OpenCV |
| [`backend/`](backend/README.md) | REST API, logins, business rules | Python, FastAPI, SQLAlchemy |
| [`web/`](web/README.md) | Customer registration, customer account, admin app | React, TypeScript, Vite |
| [`database/`](database/README.md) | Schema, migrations, seed data | PostgreSQL, Alembic |

## How the parts talk to each other

```
 camera ──> recognition (Raspberry Pi) ──HTTP──> backend ──> database
                                                   ^
 browser (customer / admin) ──> web ──────HTTP─────┘
```

The door program only turns a face into numbers (an embedding) and sends them
to the backend. The backend decides whether the door opens. Photos are never
stored.

## Status

Project skeleton only. Each folder's README says what is planned there and will
get "how to run" instructions when its first code is added.

## Setup

1. `git clone https://github.com/RicardoKohlik774/FaceGate.git`
2. Create a Python 3.12 virtual environment on this PC: `py -3.12 -m venv .venv`
   (never copy `.venv` from another PC – it stores that PC's paths).
3. Copy `.env.example` to `.env` and fill in the values. Never commit `.env`.

Only sandbox / test modes of BankID and the payment gateway are used.
