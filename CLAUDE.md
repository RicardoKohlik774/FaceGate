# FaceGate

FaceGate (working name) is a self-service entry system that replaces the reception desk in small facilities (gyms, coworking spaces, workshops, clubs). It works like a self-checkout: a customer registers and pays online, takes a selfie, and from then on a camera at the door recognizes their face, checks they have a valid membership, and opens the door. No cards, no chips, no receptionist.

This is a 4th-year school project (ročníkový projekt) at SPŠE Ječná, Prague. The author is a student who must be able to explain every part of the code at the final defense.

## Core features

1. **Self-service registration** (web, mobile-friendly)
   - Identity verification via Czech bank identity (BankID) - use the BankID sandbox / developer environment, never production
   - Buy a membership and pay online - use a payment gateway in test mode (e.g. Stripe test mode or GoPay sandbox)
   - Take a live selfie in the browser via the camera (not an upload from gallery) and store face data on the user's profile
   - Consent that the face is used only for recognition at entry
2. **Entry / exit recognition** (Raspberry Pi + camera)
   - Two cameras: one outside (entry), one inside (exit). The camera that saw the person decides the direction
   - Check membership validity; if valid, open the door (relay on a GPIO pin), otherwise deny
   - Basic liveness check so a photo on a phone cannot fool the camera
   - Fallback when the face is not recognized (e.g. PIN)
3. **Admin web app** (login required)
   - Who is inside right now
   - Entry history with filters (person, date)
   - Statistics (visits per day/hour, occupancy)
   - User management (deactivate, delete including all their data)
   - CSV export
4. **Customer account**
   - See own membership and visit history
   - Delete own account and all data

## Architecture and stack

```
FaceGate/
├── CLAUDE.md
├── recognition/   # Python - runs on the Raspberry Pi: camera capture, face recognition, liveness, door relay
├── backend/       # Python FastAPI - REST API, auth, business logic
├── web/           # React + TypeScript (Vite) - customer registration + admin app
└── database/      # PostgreSQL schema, migrations, seed data
```

- Recognition: Python, OpenCV + a face recognition library (face_recognition / dlib or InsightFace). Talks to the backend over the REST API.
- Backend: FastAPI, SQLAlchemy, PostgreSQL, JWT auth for admin. Secrets in `.env` (never committed).
- Web: React + TypeScript.
- Personal data stays on our own server (no third-party cloud for face data). Face data and the database should be encrypted at rest where practical.

If a stack choice above turns out to be a bad fit, propose an alternative and explain why before switching.

## Current situation

- Developing on Windows in PyCharm, project at `D:\C4a_kohlik\FaceGate`, Python 3.12 venv in `.venv`.
- Only one camera available for now. Simulate the second camera (exit) with a laptop webcam or a video file. Mock the door relay when not running on a Pi (just log "door opened").
- Code will later run on a Raspberry Pi; keep the recognition module runnable on both Windows and the Pi.
- Code is versioned with git (GitHub).

## Rules

- All code in English: identifiers, comments, strings, commit messages. Czech only in user-facing UI text where it makes sense.
- Work in small steps, one part at a time. Before a bigger change, write a short plan and wait for approval.
- After each change, briefly explain what you did and why, in plain language - the author must understand and defend the code.
- Keep things simple and readable over clever. No unnecessary frameworks or abstractions.
- Never commit secrets, API keys, `.env` files, face images or face data. Keep `.gitignore` up to date.
- Use sandbox / test modes for BankID and payments. Never touch production services.
- Write basic tests for backend logic (pytest).
- Every folder has a short README.md explaining what it does and how to run it.
