# FaceGate – design

This document describes how FaceGate is built: the parts, the database, the
API, how entry and exit work, the face recognition and liveness check, the
registration flow, and the order in which it is built. The current state is in
the [README](../README.md).

## Main ideas

1. **The door device is "thin", the backend decides.** The Raspberry Pi finds a
   face, checks liveness and turns the face into a list of 128 numbers (an
   *embedding*). It sends only those numbers to the backend. The backend finds
   whose face it is, checks the membership, writes the log and answers "open"
   or "deny". Face data and business rules live in one place (the server), a
   stolen Pi contains no personal data, and the membership check needs the
   server anyway.
2. **Embeddings are stored, never photos.** The selfie and camera frames are
   processed in memory and thrown away. This keeps personal data to a minimum
   (GDPR data minimisation); a leaked embedding is much less harmful than a
   leaked photo.
3. **Every external service has a mock.** BankID, the payment gateway, the door
   relay and the cameras can each be replaced by a fake through configuration,
   so the system can be developed and shown without internet, without a Pi or
   with one camera.

---

## 1. Folder structure

```
FaceGate/
├── README.md                 # what the project is and its current state
├── .gitignore                # .env, .venv, models, face data, videos, node_modules
├── .env.example              # names of all secrets, no real values
├── docs/PLAN.md              # this document
│
├── recognition/              # runs on the Pi (and on Windows for development)
│   ├── README.md
│   ├── pyproject.toml        # makes face_core installable by the backend too
│   ├── face_core/            # SHARED face code – used by the Pi AND the backend
│   │   ├── detector.py       # find faces in an image (YuNet)
│   │   ├── embedder.py       # face -> 128 numbers (SFace)
│   │   ├── liveness.py       # real face or photo/screen?
│   │   └── models/           # .onnx model files (downloaded, not committed)
│   ├── gate/                 # the door program
│   │   ├── main.py           # main loop over all configured cameras
│   │   ├── config.py         # reads config.toml
│   │   ├── camera.py         # one camera source (camera index OR video file)
│   │   ├── door.py           # MockDoor (logs) / GpioDoor (relay on the Pi)
│   │   ├── keypad.py         # fallback code input
│   │   └── backend_client.py # HTTP calls to the backend
│   ├── scripts/              # model download, demos
│   ├── config.example.toml
│   └── tests/
│
├── backend/
│   ├── README.md
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py           # creates the FastAPI app, registers routers
│   │   ├── config.py         # settings from .env
│   │   ├── db.py             # database connection / session
│   │   ├── models.py         # SQLAlchemy tables
│   │   ├── schemas.py        # request/response shapes (Pydantic)
│   │   ├── security.py       # password hashing, JWT, device keys, encryption
│   │   ├── routers/          # auth.py, me.py, payments.py, recognition.py, admin.py
│   │   └── services/         # bankid.py, payments.py, face_matching.py,
│   │                         # access.py (open/deny + visits), stats.py
│   └── tests/                # pytest
│
├── web/                      # ONE React app: /register, /account, /admin
│   ├── README.md
│   ├── package.json, vite.config.ts
│   └── src/
│       ├── api/              # small typed fetch client
│       ├── pages/register/   # Start, Plan, PaymentResult, Consent, Selfie, Done
│       ├── pages/account/    # Membership, Visits, DeleteAccount
│       ├── pages/admin/      # Login, Presence, History, Stats, Users
│       └── components/
│
└── database/
    ├── README.md             # schema description
    ├── alembic.ini
    ├── migrations/           # Alembic migration files
    └── seed.py               # demo plans, devices and users
```

Why:
- **`face_core` is shared.** The selfie (backend) and the door camera (Pi) must
  produce embeddings with exactly the same model, otherwise they cannot be
  compared. One small package used by both guarantees that.
- **One web app, not two.** Customer and admin pages share the API client and
  build setup; routes separate them.
- **Routers vs services in the backend.** Routers only handle HTTP; services
  hold the logic. That makes the logic easy to test with pytest without a web
  server.
- **Alembic for migrations**, the standard partner of SQLAlchemy: every schema
  change is a versioned file in git, so every machine builds the same database
  with one command.

---

## 2. Database schema (PostgreSQL)

Conventions: integer `id` primary keys, all times `TIMESTAMPTZ` (stored in
UTC), money as an integer number of whole Czech crowns (no rounding errors;
Stripe counts in haléře, so only the Stripe call multiplies by 100), status
columns are `TEXT` with a `CHECK` constraint (easier to change than PostgreSQL
enums). Every constraint has a fixed name, such as `ck_users_status`.

### users – customers
| column | type | note |
|---|---|---|
| id | INT PK | |
| bankid_sub | TEXT UNIQUE | stable user ID from BankID; this is how a returning customer is recognised |
| first_name, last_name | TEXT | from BankID |
| email | TEXT UNIQUE | from BankID |
| status | TEXT | `pending` (registration not finished) / `active` / `deactivated` |
| created_at | TIMESTAMPTZ | |

No password column: customers log in with BankID, so no customer passwords are
stored at all.

### admins – staff
| column | type | note |
|---|---|---|
| id | INT PK | |
| email | TEXT UNIQUE | |
| password_hash | TEXT | argon2 hash, never the password |
| is_active | BOOL | |
| created_at, last_login_at | TIMESTAMPTZ | |

Separate from `users` on purpose: different login method, different data, and a
bug in customer code can never give someone admin rights.

### consents – proof of what the user agreed to
| column | type | note |
|---|---|---|
| id | INT PK | |
| user_id | FK users, CASCADE | |
| consent_type | TEXT | `terms` / `face_biometrics` |
| document_version | TEXT | which text version they saw |
| granted_at | TIMESTAMPTZ | |
| revoked_at | TIMESTAMPTZ NULL | revoking `face_biometrics` deletes the embeddings |

A separate table (not a boolean on `users`), because it must be possible to
prove *when* and *which text* was accepted, and consent can be withdrawn and
given again.

### face_embeddings – the face data
| column | type | note |
|---|---|---|
| id | INT PK | |
| user_id | FK users, CASCADE | several rows per user allowed (e.g. 3 selfie frames) |
| embedding_encrypted | BYTEA | 128 numbers, encrypted with a key from `.env` |
| model_name | TEXT | e.g. `sface_2021dec`; embeddings from different models are not comparable |
| created_at | TIMESTAMPTZ | |

Encrypted in the application (Fernet), so a stolen database dump alone does not
reveal face templates. Matching happens in backend memory (decrypt all,
compare). For hundreds of users that takes well under a millisecond, so no
vector database is needed.

### membership_plans – what can be bought
`id`, `name`, `duration_days INT`, `price_czk INT` (whole crowns), `is_active BOOL`.

### memberships – what a user bought
| column | type | note |
|---|---|---|
| id | INT PK | |
| user_id | FK users, CASCADE | |
| plan_id | FK membership_plans | |
| status | TEXT | `pending_payment` / `active` / `cancelled` |
| valid_from, valid_until | TIMESTAMPTZ NULL | set when the payment is confirmed |
| created_at | TIMESTAMPTZ | |

"Has a valid membership" = a row with `status='active'` and
`valid_from <= now < valid_until`.

### payments
| column | type | note |
|---|---|---|
| id | INT PK | |
| user_id | FK users, SET NULL | |
| membership_id | FK memberships, SET NULL | |
| provider | TEXT | `stripe` / `mock` |
| provider_session_id | TEXT UNIQUE | the gateway's ID; UNIQUE stops double processing |
| amount_czk | INT | whole crowns |
| status | TEXT | `created` / `paid` / `failed` |
| created_at, paid_at | TIMESTAMPTZ | |

Separate from `memberships`, because one is "money" and the other is "right to
enter": a payment can fail or be retried without touching the membership logic.
Card data is never stored; the gateway handles it.

### devices – cameras at the door
| column | type | note |
|---|---|---|
| id | INT PK | |
| name | TEXT | "Front door – outside" |
| direction | TEXT | `entry` / `exit` |
| api_key_hash | TEXT | the device logs in with a secret key; only its hash is stored |
| is_active | BOOL | |
| last_seen_at | TIMESTAMPTZ | |

### access_events – raw log of everything the door saw
| column | type | note |
|---|---|---|
| id | INT PK | |
| device_id | FK devices | |
| direction | TEXT | copied from the device at that moment |
| user_id | FK users, SET NULL | NULL = unknown face |
| method | TEXT | `face` / `code` |
| result | TEXT | `granted` / `denied` |
| reason | TEXT | `ok`, `unknown_face`, `no_valid_membership`, `user_deactivated`, `liveness_failed`, `bad_code` |
| similarity | FLOAT NULL | match score, used to tune the threshold |
| occurred_at | TIMESTAMPTZ | indexed |

### visits – one row per stay (entry + exit pair)
| column | type | note |
|---|---|---|
| id | INT PK | |
| user_id | FK users, SET NULL | |
| entered_at | TIMESTAMPTZ | |
| exited_at | TIMESTAMPTZ NULL | NULL = still inside |
| close_reason | TEXT NULL | `exit` / `reentry` / `auto_closed` |

Why two tables: `access_events` is the security log (including denied attempts
and strangers); `visits` is the business view. "Who is inside now" is simply
`WHERE exited_at IS NULL`, and occupancy and visit length need no complicated
SQL.

### entry_codes – fallback when the face is not recognised
`id`, `user_id FK CASCADE`, `code_hash TEXT`, `expires_at`, `used_at NULL`. A
6-digit one-time code the customer generates in their account, valid about 2
minutes, usable once. A one-time code instead of a permanent PIN, because a
short permanent PIN is easy to guess and to share.

### Relations and deletion
```
users 1─N consents, face_embeddings, memberships, entry_codes   (deleted with the user)
users 1─N payments, access_events, visits                       (kept, user_id set to NULL)
membership_plans 1─N memberships 1─N payments
devices 1─N access_events
```
"Delete account and all data" removes everything personal (name, e-mail, face,
consents, memberships). Visit and event rows stay but become anonymous, so
statistics do not change. Payment rows stay anonymous, because a real business
must keep accounting records.

---

## 3. Main API endpoints

All under `/api`. Three kinds of caller, three kinds of authentication:
- **Customer** – session cookie (JWT, HttpOnly) set after BankID login.
- **Admin** – JWT cookie after e-mail + password login, with an `admin` role inside.
- **Device** – secret key in the `X-Device-Key` header.

### Registration and login (customer)
| method | path | what it does |
|---|---|---|
| GET | `/auth/bankid/login` | redirects the browser to BankID |
| GET | `/auth/bankid/callback` | BankID returns here; creates or finds the user, sets the session cookie, redirects to the web |
| POST | `/auth/logout` | clears the cookie |
| GET | `/plans` | list of membership plans (public) |
| POST | `/me/consents` | saves a consent (type + text version) |
| POST | `/me/face` | receives selfie frames; checks one face + liveness, stores the embedding, discards the image |

### Payment
| method | path | what it does |
|---|---|---|
| POST | `/payments/checkout` | creates a pending membership + payment, returns the gateway's payment page URL |
| POST | `/payments/webhook` | called by the gateway; verifies the signature, marks the payment paid, activates the membership |
| GET | `/payments/{id}` | payment status, for the "thank you" page |

### Customer account
| method | path | what it does |
|---|---|---|
| GET | `/me` | profile and which registration steps are done |
| GET | `/me/memberships` | current and past memberships |
| GET | `/me/visits` | own visit history |
| POST | `/me/entry-code` | generates a one-time fallback code |
| DELETE | `/me/face` | withdraws face consent and deletes embeddings |
| DELETE | `/me` | deletes the account and all data |

### Recognition (called by the door device)
| method | path | what it does |
|---|---|---|
| POST | `/recognition/identify` | body: embedding + liveness result. Finds the user, checks the membership, logs the event, updates the visit. Returns `granted`/`denied` + reason + first name |
| POST | `/recognition/code` | the same decision using the fallback code |
| POST | `/recognition/heartbeat` | "I am alive", updates `last_seen_at` |

The direction is **not** in the request body. The backend reads it from the
device that owns the key, so a device cannot lie about being the entry or exit
camera.

### Admin
| method | path | what it does |
|---|---|---|
| POST | `/admin/login` | e-mail + password → JWT |
| GET | `/admin/presence` | who is inside right now |
| GET | `/admin/events` | history with filters `user_id`, `from`, `to`, `result`, paging |
| GET | `/admin/events/export.csv` | the same filters, as a CSV file |
| GET | `/admin/stats/visits` | visits per day or per hour |
| GET | `/admin/stats/occupancy` | people inside over time for one day |
| GET | `/admin/users`, `/admin/users/{id}` | list / detail |
| POST | `/admin/users/{id}/deactivate`, `/activate` | block or unblock a user |
| DELETE | `/admin/users/{id}` | delete the user and all their data |
| GET/POST | `/admin/devices` | list / register a device (key shown once) |
| GET/POST/PATCH | `/admin/plans` | manage membership plans |

---

## 4. Entry vs exit with two cameras

**Rule: the camera decides the direction.** Each camera is registered in
`devices` with a direction and its own key. Whatever that camera recognises is
an entry (or exit) event.

What the door program does for each camera, in a loop:
1. Read a frame.
2. Find the largest face; ignore faces that are too small (person still far away)
   or too close (see liveness).
3. Liveness check over several frames.
4. Compute the embedding and send it to `/recognition/identify` with that
   camera's key.
5. If the answer is `granted`, switch the relay for about 3 seconds.
6. Wait a few seconds before the same camera's next request (cooldown), so one
   person does not create ten events.

What the backend does:
- **Entry:** known face + active user + valid membership → `granted`, open a new
  visit. If the user already has an open visit (the exit was missed), the old
  one is closed as `reentry` first.
- **Exit:** known face → `granted`, close the open visit. The membership is
  **not** checked on exit: nobody may be trapped inside because their
  membership expired an hour ago.
- **Stale visits:** a visit open longer than e.g. 12 hours is closed as
  `auto_closed`, because some people leave without being seen.

**Camera sources.** OpenCV opens a camera and a video file with the same call
(`cv2.VideoCapture(0)` is camera number 0, `cv2.VideoCapture("exit.mp4")` is a
file), so the source of each camera is one value in the configuration:

```toml
[[camera]]
name = "entry"
source = 0
device_key = "..."

[[camera]]
name = "exit"
source = 1                       # or a video file
device_key = "..."
```

One program reads both cameras in turn (a frame from A, a frame from B,
repeat). One program, not two, because both cameras control the same door
relay, and a GPIO pin can be owned by only one process.

The door is the same idea: `MockDoor` writes "door opened" to the log,
`GpioDoor` switches the relay. The configuration picks which one, so the same
code runs on Windows and on the Pi.

---

## 5. Face recognition and liveness

### OpenCV's own models: YuNet (detection) + SFace (recognition)

| | YuNet + SFace (OpenCV) | face_recognition (dlib) | InsightFace |
|---|---|---|---|
| Install on Windows | `pip install opencv-python`, done | must compile dlib (CMake + Visual Studio) – often fails | needs a C++ compiler too |
| Install on the Pi | the same one package | compiling takes very long | heavier, more dependencies |
| Speed on a Pi 4 | detection a few ms, embedding about 100 ms | slow detector | slowest with the accurate model |
| Accuracy (LFW test set) | about 99.6 % | about 99.4 % | best of the three |
| Licence of the models | free, also commercial | free | non-commercial research only |
| Maintained | yes (part of OpenCV) | no real updates for years | yes |

YuNet and SFace are already inside OpenCV, which is needed for the camera
anyway; they install identically on Windows and the Pi with one command; they
are fast enough on a Pi; and their licence allows real use. InsightFace is more
accurate, but for a facility with tens or hundreds of members SFace is enough.
Switching later is cheap: only `face_core/embedder.py` changes, and everyone
re-takes their selfie (that is why `model_name` is stored). The OpenCV version
is pinned, because the PC and the Pi must compute embeddings the same way.

**How a match is decided:** two embeddings are compared with cosine similarity
(1 = same direction, 0 = unrelated). The backend compares the door embedding
with all stored ones, takes the best, and accepts it only from 0.40 up.
OpenCV suggests 0.363; a slightly stricter value lets fewer strangers in, at
the cost of rejecting a member a little more often. The `similarity` saved in
`access_events` is used to tune it.

### Liveness: a small anti-spoofing model over several frames

**MiniFASNet** (from the "Silent Face Anti-Spoofing" project, Apache-2.0
licence; the ONNX version from `facenox/face-antispoof-onnx`) is a small neural
network trained to tell a real face from a photo or a screen, using texture,
screen glare and edges. It runs through OpenCV's own DNN module, so no extra
library is needed, and it needs no action from the person, which keeps the door
as fast as a self-checkout. The same check runs on the selfie at registration.

Rules on top of the model:
- **8 "real" frames in a row** are needed before anything is sent to the
  backend; one spoof frame or a frame without a face starts the count again.
- **A face wider than 22 % of the picture is too close** ("step back") and
  cannot pass: in tests, a tilted tablet held close to the camera could fool
  the model, while a person at the door stands further away.

This is a *basic* check. In tests it blocked a photo on a phone and on a
monitor. It needs good light at the door, and it will not reliably stop a
high-quality video or a 3D mask; commercial systems use infrared or depth
cameras for that. A head-turn challenge computed from YuNet's five face points
is the planned extra layer if stronger protection is needed.

---

## 6. Registration flow with BankID and payment

### Step by step
```
1. /register            "Start" → the browser goes to BankID
2. BankID sandbox       the user logs in with a sandbox test person
3. callback             backend creates the user (status pending), sets the session cookie
4. Terms                the user accepts the terms            → consents row
5. Plan                 the user picks a membership
6. Payment page         hosted by the gateway, paid with a test card
7. Webhook              the gateway tells the backend "paid"  → membership becomes active
8. Face consent         explicit biometric consent            → consents row
9. Selfie               live camera in the browser            → embedding stored
10. Done                user status = active
```
Identity first, so every later step belongs to a verified person. Payment
before the selfie, so no biometric data is held of people who did not finish
buying. Consent strictly before the camera turns on. If the selfie step fails,
the user has still paid, can enter with the fallback code and retry the selfie
from their account.

### BankID (Czech Bank iD)
Standard **OpenID Connect, authorization code flow** – the same mechanism as
"Log in with Google":
1. An application registered on the Bank iD developer portal has a sandbox
   `client_id` and `client_secret` (in `.env`) and our callback address.
2. `/auth/bankid/login` redirects to the sandbox (`https://oidc.sandbox.bankid.cz/auth`)
   with a random `state`.
3. The user logs in there. BankID redirects back with a one-time `code`.
4. The backend exchanges the `code` for tokens (server to server, using the
   secret), verifies the ID token, and reads the name and e-mail.
5. The user is found or created by `sub` (BankID's stable ID).

The same flow is the customer login later, so there is no separate password
system.

`BANKID_MODE=mock|sandbox` in `.env`: in `mock` mode the backend shows its own
small "choose a test person" page instead of going to BankID, so registration
also works without the sandbox. Production addresses are never configured.

### Payments: Stripe in test mode
A Stripe test account works minutes after sign-up, the payment page is hosted
by Stripe (card numbers never touch our server), and the Stripe CLI delivers
webhooks to `localhost`.

1. `/payments/checkout` creates a Stripe Checkout Session (plan name, price in
   CZK, our payment ID) and returns its URL.
2. The user pays on Stripe's page with the test card `4242 4242 4242 4242`.
3. Stripe calls `/payments/webhook` with `checkout.session.completed`. The
   backend verifies the signature, marks the payment `paid`, and sets the
   membership `active` with `valid_from`/`valid_until`.
4. The browser returns to our "thank you" page, which only *reads* the status.

**The membership is activated only by the webhook, never by the browser
returning to the success page**, because anyone can type that address by hand.
The webhook can arrive twice, so the handler first checks whether the payment
is already `paid`. A membership is a one-time purchase for a number of days.

`PAYMENT_MODE=mock|stripe`: the mock is a fake payment page with "Pay" and
"Fail" buttons. Only test keys (`sk_test_…`) are ever used.

---

## 7. Order of implementation

Each step ends with something that can be run and shown. The riskiest
technology comes first.

| # | Step | What works afterwards |
|---|---|---|
| 0 | Skeleton: folders, READMEs, `.gitignore`, `.env.example` | clean repository |
| 1 | `face_core`: webcam → detect → embedding → compare with a saved face | "match / no match" on the webcam |
| 2 | Liveness: anti-spoofing model on the webcam, tested with photos and screens | basic liveness check |
| 3 | Backend skeleton: FastAPI, PostgreSQL, Alembic, first tables, seed script, pytest | API runs, database has demo data |
| 4 | `/recognition/identify`, device keys, face matching, an enrol script; door program with `MockDoor` | **Milestone A:** stand in front of the camera → log says "door opened" |
| 5 | Second camera, visits logic, tests for the edge cases | entry and exit both work, "inside" list is correct |
| 6 | Admin: login, presence, history with filters, CSV; admin web pages | admin sees live who is inside |
| 7 | Registration with mock BankID + mock payment: consent pages, live selfie, `/me/face` | **Milestone B:** register in the browser, walk to the camera, door opens |
| 8 | Stripe test mode replaces the mock payment | a test payment activates the membership |
| 9 | BankID sandbox replaces the mock login | real sandbox identity |
| 10 | Customer account: memberships, visits, fallback code, delete account; admin deactivate/delete | all four feature groups exist |
| 11 | Statistics pages (visits per day/hour, occupancy) | charts in admin |
| 12 | Raspberry Pi: real relay on GPIO, keypad, autostart | **Milestone C:** real door hardware |
| 13 | Hardening: HTTPS, login rate limits, threshold tuning, final READMEs and tests | ready for the defence |

---

## 8. Hardware and environment

- **Door device:** Raspberry Pi 3 Model B with 64-bit Raspberry Pi OS (Debian
  13). It runs only the door program; the backend and the database run on a
  PC, because the Pi 3 has 1 GB of RAM. It uses `opencv-python-headless`, the
  same OpenCV version without windows, because the Pi has no desktop.
- **Cameras:** two Logitech Brio 300 USB webcams (entry and exit). Plain OpenCV
  capture works the same on Windows and on the Pi.
- **Speed on the Pi 3:** about 2.6 s from a face to a decision with one camera
  at 640x480. Face detection is the slowest step, so the door program can
  detect on a smaller picture.
- **Database:** PostgreSQL 18, accessed through SQLAlchemy with the pure-Python
  driver `pg8000` (Windows' Smart App Control blocks the compiled driver).
- **If the Pi is not available,** the door program also runs on a laptop with a
  webcam.

---

## 9. Privacy and risks

**Legal / privacy**
- A face template is *biometric data*, a special category under GDPR. It needs
  explicit consent, and consent is only valid if the person has a real
  alternative – that is what the fallback code is for.
- Only the author and people who agreed are used for testing. No real customers.
- BankID proves who owns the account, but nothing proves that the selfie shows
  the same person: a member could enrol a friend's face. A known limit.

**Technical**
- **Liveness is basic** and depends on the camera and the light (section 5).
- **Phone selfie vs door camera** look different (light, angle), which lowers
  match scores. Several selfie frames, good light at the door and threshold
  tuning help.
- **Wrong person accepted vs member rejected** is a trade-off set by one
  number. Twins and close relatives can match.
- **Network or backend down = door stays closed.** This is the price of the
  thin door device; a local cache would be a later extension.
- **Tailgating and unseen exits** make the "inside" list imperfect. Auto-closing
  old visits limits the damage.
- **Fire safety:** the door must always open from the inside by hand, without
  the system and without power.
- **The browser camera only works on HTTPS or `localhost`.** Testing the selfie
  from a phone against a laptop needs a local HTTPS certificate.
- **The encryption key sits next to the data** on a small server. Application
  encryption protects a leaked database dump, not a stolen machine; disk
  encryption (BitLocker / LUKS) covers that part.
- **External sandboxes can be down** – the mock modes are the insurance.

---

## 10. How each milestone is checked

- **Backend logic:** `pytest` in `backend/` – membership validity, match
  threshold, entry/exit/visit edge cases, webhook handled twice, account
  deletion leaves no personal data.
- **Milestone A:** backend + door program running; a seeded user in front of
  the camera gives `granted` in the log and a row in `access_events`; a stranger
  gives `denied / unknown_face`; a phone photo gives `liveness_failed`.
- **Entry/exit:** `/admin/presence` shows the person after entry and not after
  exit.
- **Milestone B:** in the browser: mock BankID → pay → selfie; then the door
  camera opens for that new user. With an expired membership it denies.
- **Payments:** `stripe listen --forward-to localhost:8000/api/payments/webhook`,
  pay with the test card, the membership becomes active; opening the success
  URL by hand without paying activates nothing.
- **Deletion:** delete an account, then check in the database that no name,
  e-mail, embedding or consent of that user remains.

## Sources
- Bank iD developer portal – https://developer.bankid.cz/docs/apis , https://developer.bankid.cz/docs/high_level_overview_sep
- OpenCV face tutorial (SFace accuracy, thresholds) – https://docs.opencv.org/4.5.4/d0/dd4/tutorial_dnn_face.html
- OpenCV Zoo benchmarks (Raspberry Pi 4 timings) – https://github.com/opencv/opencv_zoo/blob/master/benchmark/README.md
- Anti-spoofing ONNX model – https://github.com/facenox/face-antispoof-onnx
- Stripe CLI and Checkout fulfilment – https://docs.stripe.com/stripe-cli/use-cli , https://docs.stripe.com/checkout/fulfillment
