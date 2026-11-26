# FaceGate

Self-service entry system for small facilities (gyms, coworking spaces, clubs).
A customer registers and pays online, takes a selfie, and from then on a camera
at the door recognises their face, checks the membership and opens the door.
No cards, no chips, no receptionist.

School project (ročníkový projekt), SPŠE Ječná, Prague, 2026/2027.

## Status (November 2026)

| Part | State |
|---|---|
| Face recognition | **Works.** Detection (YuNet) and recognition (SFace) on a webcam: the enrolled person scores about 0.75, another person about 0.2, the limit is 0.40. |
| Liveness (photo or real face?) | **Works as a basic check.** In good light it blocked a photo on a phone and on a monitor. Known limits: it needs good light, and a close, tilted iPad got through before a "too close" rule was added. |
| Raspberry Pi 3 | **Runs the face code** (64-bit system, all tests pass). About 2.6 s from a face to a decision with one camera; to be sped up. |
| Database | **Ready.** PostgreSQL with the first 7 tables (users, memberships, devices, entry log, visits …) and demo data. The database itself refuses wrong data. |
| Backend | **Skeleton runs.** FastAPI with a health check; tests for the tables and rules. |
| Door program, admin, registration, payments | Not started yet. |

Next: **Milestone A** – a person stands in front of the camera, the backend
checks the face and the membership, and the door program logs "door opened"
(or "denied" with a reason).

The detailed log, test results and decisions are in
[`docs/PROGRESS.md`](docs/PROGRESS.md); the whole design is in
[`docs/PLAN.md`](docs/PLAN.md).

## Plan

| When | What |
|---|---|
| until mid-December | Door program + recognition API (Milestone A), entry and exit with two cameras, who is inside |
| Christmas | reserve |
| January | Admin web, registration with BankID sandbox, test payment and live selfie (Milestone B), customer account |
| February | Real door relay on the Pi (Milestone C), final tests, documentation |

## Parts

| Folder | What it is | Technology |
|---|---|---|
| [`recognition/`](recognition/README.md) | Door program: camera, face recognition, liveness, door relay | Python, OpenCV |
| [`backend/`](backend/README.md) | REST API, logins, business rules | Python, FastAPI, SQLAlchemy |
| [`web/`](web/README.md) | Customer registration, customer account, admin app | React, TypeScript, Vite |
| [`database/`](database/README.md) | Schema, migrations, seed data | PostgreSQL, Alembic |

Each folder's README explains how to run it.

## How the parts talk to each other

```
 camera ──> recognition (Raspberry Pi) ──HTTP──> backend ──> database
                                                   ^
 browser (customer / admin) ──> web ──────HTTP─────┘
```

The door program only turns a face into numbers (an embedding) and sends them
to the backend. The backend decides whether the door opens. Photos are never
stored; the face numbers are stored encrypted.

Only sandbox / test modes of BankID and the payment gateway are used.
