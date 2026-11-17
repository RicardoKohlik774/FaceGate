# FaceGate – whole-project plan

## Context

Approved on 2026-11-11. This is the design for the whole project. What is already done, decisions made since the approval, and the next step are in [`PROGRESS.md`](PROGRESS.md). We go one small step at a time (section 7), each with its own short plan.

Three decisions shape everything else, so they come first:

1. **The door device is "thin", the backend decides.** The Pi finds a face, checks liveness and turns the face into a list of 128 numbers (an *embedding*). It sends only those numbers to the backend. The backend finds whose face it is, checks the membership, writes the log and answers "open" or "deny". Why: face data and business rules live in one place (the server), a stolen Pi contains no personal data, and the membership check needs the server anyway.
2. **We store embeddings, never photos.** The selfie and camera frames are processed in memory and thrown away. Why: least data possible (GDPR data minimisation); a leaked embedding is much less harmful than a leaked photo.
3. **Every external service has a mock.** BankID, the payment gateway, the door relay and the second camera can each be replaced by a fake through configuration. Why: you can develop and present the project even with no internet, no Pi and one camera.

---

## 1. Folder structure

```
FaceGate/
├── CLAUDE.md
├── README.md                 # what the project is, how to start all parts
├── .gitignore                # .env, .venv, models, face data, videos, node_modules
├── .env.example              # names of all secrets, no real values
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
│   ├── scripts/download_models.py
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
    ├── README.md             # schema description + ER diagram
    ├── alembic.ini
    ├── migrations/           # Alembic migration files
    └── seed.py               # plans, one admin, two devices, demo users
```

Why these choices:
- **`face_core` is shared.** The selfie (backend) and the door camera (Pi) must produce embeddings with exactly the same model, otherwise they cannot be compared. One small package used by both guarantees that. It lives in `recognition/` so we keep the four top-level folders from `CLAUDE.md`.
- **One web app, not two.** Customer and admin pages share the API client and build setup; routes separate them.
- **Routers vs services in the backend.** Routers only handle HTTP; services hold the logic. That makes the logic easy to test with pytest without a web server.
- **Alembic for migrations** because it is the standard partner of SQLAlchemy and every schema change becomes a versioned file in git.

---

## 2. Database schema (PostgreSQL)

Conventions: integer `id` primary keys, all times `TIMESTAMPTZ` (stored in UTC), money as integer in haléře (no float rounding errors), status columns are `TEXT` with a `CHECK` constraint (easier to change than PostgreSQL enums).

### users – customers
| column | type | note |
|---|---|---|
| id | INT PK | |
| bankid_sub | TEXT UNIQUE | stable user ID from BankID; this is how we recognise a returning customer |
| first_name, last_name | TEXT | from BankID |
| email | TEXT UNIQUE | from BankID |
| status | TEXT | `pending` (registration not finished) / `active` / `deactivated` |
| created_at | TIMESTAMPTZ | |

No password column: customers log in with BankID, so we store no customer passwords at all.

### admins – staff
| column | type | note |
|---|---|---|
| id | INT PK | |
| email | TEXT UNIQUE | |
| password_hash | TEXT | argon2 hash, never the password |
| is_active | BOOL | |
| created_at, last_login_at | TIMESTAMPTZ | |

Separate from `users` on purpose: different login method, different data, and a bug in customer code can never give someone admin rights.

### consents – proof of what the user agreed to
| column | type | note |
|---|---|---|
| id | INT PK | |
| user_id | FK users, CASCADE | |
| consent_type | TEXT | `terms` / `face_biometrics` |
| document_version | TEXT | which text version they saw |
| granted_at | TIMESTAMPTZ | |
| revoked_at | TIMESTAMPTZ NULL | revoking `face_biometrics` deletes the embeddings |

A separate table (not a boolean on `users`) because we must be able to prove *when* and *which text* was accepted, and consent can be withdrawn and given again.

### face_embeddings – the face data
| column | type | note |
|---|---|---|
| id | INT PK | |
| user_id | FK users, CASCADE | several rows per user allowed (e.g. 3 selfie frames) |
| embedding_encrypted | BYTEA | 128 floats, encrypted with a key from `.env` |
| model_name | TEXT | e.g. `sface_2021dec`; embeddings from different models are not comparable |
| created_at | TIMESTAMPTZ | |

Encrypted in the application (Fernet), so a stolen database dump alone does not reveal face templates. Matching happens in backend memory (decrypt all, compare). For hundreds of users that takes well under a millisecond, so no vector database is needed.

### membership_plans – what can be bought
`id`, `name`, `duration_days INT`, `price_minor INT` (haléře), `currency TEXT`, `is_active BOOL`.

### memberships – what a user bought
| column | type | note |
|---|---|---|
| id | INT PK | |
| user_id | FK users, CASCADE | |
| plan_id | FK membership_plans | |
| status | TEXT | `pending_payment` / `active` / `cancelled` |
| valid_from, valid_until | TIMESTAMPTZ NULL | set when the payment is confirmed |
| created_at | TIMESTAMPTZ | |

"Has valid membership" = a row with `status='active'` and `valid_from <= now < valid_until`.

### payments
| column | type | note |
|---|---|---|
| id | INT PK | |
| user_id | FK users, SET NULL | |
| membership_id | FK memberships, SET NULL | |
| provider | TEXT | `stripe` / `mock` |
| provider_session_id | TEXT UNIQUE | the gateway's ID; UNIQUE stops double processing |
| amount_minor, currency | INT, TEXT | |
| status | TEXT | `created` / `paid` / `failed` |
| created_at, paid_at | TIMESTAMPTZ | |

Separate from `memberships` because one is "money" and the other is "right to enter"; a payment can fail or be retried without touching the membership logic. We never store card data: the gateway does.

### devices – cameras at the door
| column | type | note |
|---|---|---|
| id | INT PK | |
| name | TEXT | "Front door – outside" |
| direction | TEXT | `entry` / `exit` |
| api_key_hash | TEXT | the device logs in with a secret key; we store only its hash |
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
| similarity | REAL NULL | match score, needed to tune the threshold |
| occurred_at | TIMESTAMPTZ | indexed |

### visits – one row per stay (entry + exit pair)
| column | type | note |
|---|---|---|
| id | INT PK | |
| user_id | FK users, SET NULL | |
| entered_at | TIMESTAMPTZ | |
| exited_at | TIMESTAMPTZ NULL | NULL = still inside |
| close_reason | TEXT NULL | `exit` / `reentry` / `auto_closed` |

Why two tables: `access_events` is the security log (including denied attempts and strangers). `visits` is the business view. "Who is inside now" is simply `WHERE exited_at IS NULL`, and occupancy and visit length need no complicated SQL.

### entry_codes – fallback when the face fails
`id`, `user_id FK CASCADE`, `code_hash TEXT`, `expires_at`, `used_at NULL`. A 6-digit one-time code the customer generates in their account, valid about 2 minutes, usable once.

### Relations and deletion
```
users 1─N consents, face_embeddings, memberships, entry_codes   (deleted with the user)
users 1─N payments, access_events, visits                       (kept, user_id set to NULL)
membership_plans 1─N memberships 1─N payments
devices 1─N access_events
```
"Delete account and all data" removes everything personal (name, email, face, consents, memberships). Visit and event rows stay but become anonymous, so statistics do not change. Payment rows stay anonymous because a real business must keep accounting records.

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

### Recognition (called by the Pi)
| method | path | what it does |
|---|---|---|
| POST | `/recognition/identify` | body: embedding + liveness result. Finds the user, checks membership, logs the event, updates the visit. Returns `granted`/`denied` + reason + first name |
| POST | `/recognition/code` | same decision using the fallback code |
| POST | `/recognition/heartbeat` | "I am alive", updates `last_seen_at` |

The direction is **not** in the request body. The backend reads it from the device that owns the key, so a device cannot lie about being the entry or exit camera.

### Admin
| method | path | what it does |
|---|---|---|
| POST | `/admin/login` | e-mail + password → JWT |
| GET | `/admin/presence` | who is inside right now |
| GET | `/admin/events` | history with filters `user_id`, `from`, `to`, `result`, paging |
| GET | `/admin/events/export.csv` | same filters, CSV file |
| GET | `/admin/stats/visits` | visits per day or per hour |
| GET | `/admin/stats/occupancy` | people inside over time for one day |
| GET | `/admin/users`, `/admin/users/{id}` | list / detail |
| POST | `/admin/users/{id}/deactivate`, `/activate` | block or unblock a user |
| DELETE | `/admin/users/{id}` | delete the user and all their data |
| GET/POST | `/admin/devices` | list / register a device (key shown once) |
| GET/POST/PATCH | `/admin/plans` | manage membership plans |

---

## 4. Entry vs exit with two cameras

**Rule: the camera decides the direction.** Each camera is registered in `devices` with a direction and its own key. Whatever that camera recognises is an entry (or exit) event.

What the door program does for each camera, in a loop:
1. Read a frame.
2. Find the largest face; ignore faces that are too small (person still far away).
3. Liveness check over a few frames.
4. Compute the embedding and send it to `/recognition/identify` with that camera's key.
5. If the answer is `granted`, switch the relay for about 3 seconds.
6. Wait a few seconds before sending the same camera's next request (cooldown), so one person does not create ten events.

What the backend does:
- **Entry:** known face + active user + valid membership → `granted`, open a new visit. If the user already has an open visit (the exit was missed), close the old one as `reentry` first.
- **Exit:** known face → `granted`, close the open visit. Membership is **not** checked on exit: nobody may be trapped inside because their membership expired an hour ago.
- **Stale visits:** a visit open longer than e.g. 12 hours is closed as `auto_closed`, because some people will leave without being seen.

**Simulating the second camera now.** OpenCV opens a camera and a video file with the same call: `cv2.VideoCapture(0)` is camera number 0, `cv2.VideoCapture("exit_demo.mp4")` is a file. So the camera source is just one value in the configuration:

```toml
[[camera]]
name = "entry"
source = 0                       # the real camera
device_key = "..."

[[camera]]
name = "exit"
source = "samples/exit_demo.mp4" # or 1 = laptop webcam
device_key = "..."
```

One program reads both sources in turn (frame from A, frame from B, repeat). One program, not two, because both cameras control the same door relay and a GPIO pin can be owned by only one process. When the second real camera arrives, only `source` changes; no code changes.

The door is the same idea: `MockDoor` writes "door opened" to the log, `GpioDoor` switches the relay. Configuration picks which one, so the same code runs on Windows and the Pi.

---

## 5. Face recognition library and liveness

### Recommendation: OpenCV's own models – YuNet (detection) + SFace (recognition)

`CLAUDE.md` suggests `face_recognition`/dlib or InsightFace. I recommend a third option and this is why:

| | YuNet + SFace (OpenCV) | face_recognition (dlib) | InsightFace |
|---|---|---|---|
| Install on Windows, Python 3.12 | `pip install opencv-python`, done | must compile dlib (CMake + Visual Studio) – often fails | needs a C++ compiler too |
| Install on the Pi | same one package | compile takes very long | heavier, more dependencies |
| Speed on Pi 4 | detection a few ms, embedding about 100 ms | slow detector | slowest with the accurate model |
| Accuracy (LFW test set) | about 99.6 % | about 99.4 % | best of the three |
| Licence of the models | free, also commercial | free | models are for non-commercial research only |
| Maintained | yes (part of OpenCV) | no real updates for years | yes |

Simple argument for the defence: *it is already inside OpenCV, which we need anyway for the camera; it installs identically on Windows and the Pi with one command; it is fast enough on a Pi; and its licence allows real use.* InsightFace is more accurate, but for a facility with tens or hundreds of members SFace is enough, and the harder install is a real risk.

Switching later is cheap: only `face_core/embedder.py` changes, and everyone re-takes their selfie (that is why `model_name` is stored).

**How a match is decided:** two embeddings are compared with cosine similarity (1 = same direction, 0 = unrelated). The backend compares the door embedding with all stored ones, takes the best, and accepts it only above a threshold. OpenCV's suggested value is 0.363; we start a bit stricter and tune it using the `similarity` values saved in `access_events`. Stricter = fewer strangers let in, but more members rejected.

### Liveness: a small anti-spoofing model + several frames

Recommended: **MiniFASNet** (from the "Silent Face Anti-Spoofing" project, Apache-2.0 licence). It is a small neural network trained to tell a real face from a printed photo or a screen, using texture, screen glare and edges. It runs on the face crop, needs no action from the person, and we require a "real" result on several frames in a row before sending anything to the backend. The same check runs on the selfie at registration.

Why this and not blinking or "turn your head": a self-service door should be as fast as a self-checkout, and a challenge needs a screen at the door to give instructions.

What to say honestly at the defence: this is a *basic* check. It stops the common attack (photo on a phone, printed photo). It will not reliably stop a high-quality video on a good screen or a 3D mask; commercial systems use infrared or depth cameras for that.

Two things I could not confirm in advance and we will test in the first step: a ready ONNX version of the model exists in community projects but must be tried on the Pi, and its accuracy depends on the actual camera. Backup plan if it disappoints: a head-turn challenge computed from the five face points YuNet already gives us.

---

## 6. BankID sandbox and payment test mode in the registration flow

### The flow, step by step
```
1. /register            "Start" → browser goes to BankID
2. BankID sandbox       user logs in with a sandbox test person
3. callback             backend creates user (status pending), sets session cookie
4. Terms                user accepts terms             → consents row
5. Plan                 user picks a membership
6. Payment page         hosted by the gateway, paid with a test card
7. Webhook              gateway tells backend "paid"   → membership becomes active
8. Face consent         explicit biometric consent     → consents row
9. Selfie               live camera in the browser     → embedding stored
10. Done                user status = active
```
Order reasons: identity first, so every later step belongs to a verified person. Payment before selfie, so we never hold biometric data of people who did not finish buying. Consent strictly before the camera turns on. If the selfie step fails, the user has still paid and can enter with the fallback code and retry the selfie from their account.

### BankID (Czech Bank iD)
It is standard **OpenID Connect, authorization code flow** – the same mechanism as "Log in with Google":
1. Register an application on the Bank iD developer portal; get sandbox `client_id` and `client_secret` (into `.env`) and set the redirect address to our callback.
2. `/auth/bankid/login` redirects to the sandbox (`https://oidc.sandbox.bankid.cz/auth`) with a random `state`.
3. The user logs in there. BankID redirects back with a one-time `code`.
4. The backend exchanges the `code` for tokens (server to server, using the secret), verifies the ID token, and reads name and e-mail.
5. We find or create the user by `sub` (BankID's stable ID).

The same flow is the customer login later, so there is no separate password system to build.

`BANKID_MODE=mock|sandbox` in `.env`: in `mock` mode the backend shows its own tiny "choose a test person" page instead of going to BankID. Built first, so registration works before the sandbox is set up and still works if the sandbox is down on defence day. Production addresses are never configured anywhere.

### Payments: Stripe in test mode (recommended over GoPay)
Why Stripe: a test account works minutes after sign-up, the payment page is hosted by Stripe (card numbers never touch our server), and the Stripe CLI can deliver webhooks to `localhost`. GoPay is more Czech but its sandbox needs credentials requested from GoPay.

1. `/payments/checkout` creates a Stripe Checkout Session (plan name, price in CZK, our payment ID) and returns its URL.
2. The user pays on Stripe's page with the test card `4242 4242 4242 4242`.
3. Stripe calls `/payments/webhook` with `checkout.session.completed`. We verify the signature, mark the payment `paid`, and set the membership `active` with `valid_from`/`valid_until`.
4. The browser returns to our "thank you" page, which only *reads* the status.

The important rule: **the membership is activated only by the webhook, never by the browser returning to the success page**, because anyone can type that address by hand. The webhook can arrive twice, so the handler checks whether the payment is already `paid` first.

`PAYMENT_MODE=mock|stripe`: the mock gives a fake payment page with "Pay" and "Fail" buttons. Only test keys (`sk_test_…`) are ever used.

---

## 7. Order of implementation

Each step ends with something you can run and show. Riskiest technology first.

| # | Step | What works afterwards |
|---|---|---|
| 0 | Skeleton: folders, READMEs, `.gitignore`, `.env.example` | clean repo on GitHub |
| 1 | `face_core` on Windows: webcam → detect → embedding → compare with a face saved in a local file | console prints "match / no match" – proves the library choice |
| 2 | Liveness test: run the anti-spoofing model on the webcam, try a phone photo | we know if the liveness plan works (or switch to the backup now) |
| 3 | Backend skeleton: FastAPI `/health`, PostgreSQL, Alembic, first tables, seed script, pytest | API runs, database has demo data |
| 4 | `/recognition/identify` + device keys + face matching + a small enrol script; `gate` program with `MockDoor` | **Milestone A:** stand in front of the camera → log says "door opened" |
| 5 | Second camera from config (video file), visits logic, tests for the edge cases | entry and exit both work, "inside" list is correct |
| 6 | Admin: login, presence, history with filters, CSV; web admin pages | admin sees live who is inside |
| 7 | Registration with mock BankID + mock payment: consent pages, live selfie, `/me/face` | **Milestone B:** register in the browser, walk to the camera, door opens |
| 8 | Stripe test mode replaces the mock payment | real test payment activates the membership |
| 9 | BankID sandbox replaces the mock login | real sandbox identity |
| 10 | Customer account: memberships, visits, fallback code, delete account; admin deactivate/delete | all four feature groups from `CLAUDE.md` exist |
| 11 | Statistics pages (visits per day/hour, occupancy) | charts in admin |
| 12 | Raspberry Pi: install, real relay on GPIO, keypad, autostart | **Milestone C:** real door hardware |
| 13 | Hardening: HTTPS, login rate limits, threshold tuning, final READMEs and tests | ready for the defence |

Step 12 can move earlier as soon as the Pi is available. Right after step 2 we run the step 1 and step 2 scripts on the Pi 3 and measure the time per face, because speed there is a risk (see `PROGRESS.md`, hardware).

---

## 8. Open decisions and risks

**Decisions for you (my recommendation in brackets)**
1. Face library: YuNet + SFace instead of `face_recognition` or InsightFace. **Decided 2026-11-11: YuNet + SFace.**
2. Payment gateway: Stripe test mode or GoPay sandbox (Stripe). **Decided 2026-11-17: Stripe test mode.**
3. Customer login: BankID only, or also e-mail + password (BankID only – less code, no stored passwords).
4. Fallback: one-time code from the account, or a permanent personal PIN (one-time code – a 4-digit permanent PIN is easy to guess and to share). Either needs a keypad at the door; a USB numeric keypad is enough.
5. Membership: one-time purchase for N days, or automatic monthly subscription (one-time – much simpler).
6. Where do the backend and database run at the defence: your laptop, or on the Pi itself? **Decided 2026-11-11: on a PC/laptop.** The Pi 3 has 1 GB of RAM and runs only the door program.
7. PostgreSQL on Windows: Docker or a normal installation (depends on what the school PC allows).
8. Which Raspberry Pi model and camera. **Known 2026-11-11: Raspberry Pi 3.** It is slower than a Pi 4 but usable for the thin door program if it gets a 64-bit system; details in `PROGRESS.md`. **Decided 2026-11-17: USB webcam**, so plain OpenCV capture works the same on Windows and the Pi.

**Legal / privacy risks**
- A face template is *biometric data*, a special category under GDPR. It needs explicit consent, and consent is only valid if the person has a real alternative – that is exactly what the fallback code is for. Good point for the defence.
- Test only with your own face and classmates who agreed. No real customers.
- BankID proves who the account owner is, but nothing proves the selfie shows the same person. A member could enrol a friend's face. Known limit; mention it.

**Technical risks**
- **Liveness is basic** and depends on the camera (section 5). Tested in step 2.
- **Phone selfie vs door camera** look different (light, angle), which lowers match scores. Help: several selfie frames, good light at the door, threshold tuning.
- **Wrong person accepted vs member rejected** is a trade-off set by one number. Twins and close relatives can match.
- **Network or backend down = door stays closed.** This is the price of decision 1. Accepted for the project; a local cache would be a later extension.
- **Tailgating and unseen exits** make the "inside" list imperfect. Auto-closing old visits limits the damage.
- **Fire safety:** the door must always open from the inside by hand, without the system and without power.
- **The browser camera only works on HTTPS or `localhost`.** Testing the selfie from a phone against your laptop needs a local HTTPS certificate – plan time for it.
- **Stripe webhooks need to reach your PC** – solved by the Stripe CLI in development.
- **Encryption key sits next to the data** on a small server. Application encryption protects a leaked database dump, not a fully stolen machine; disk encryption (BitLocker / LUKS) covers that part.
- **External sandboxes can be down on defence day** – the mock modes are the insurance.

---

## Verification (how each milestone is checked)

- **Backend logic:** `pytest` in `backend/` – membership validity, match threshold, entry/exit/visit edge cases, webhook handled twice, account deletion leaves no personal data.
- **Milestone A:** start backend + `gate`; a seeded user in front of the camera gives `granted` in the log and a row in `access_events`; a stranger gives `denied / unknown_face`; a phone photo gives `liveness_failed`.
- **Entry/exit:** run with the video file as the exit camera; `/admin/presence` shows the person after entry and not after exit.
- **Milestone B:** in the browser: mock BankID → pay → selfie; then the door camera opens for that new user. With an expired membership it denies.
- **Payments:** `stripe listen --forward-to localhost:8000/api/payments/webhook`, pay with the test card, membership becomes active; opening the success URL by hand without paying does not activate anything.
- **Deletion:** delete an account, then check in the database that no name, e-mail, embedding or consent of that user remains.

## Sources checked
- Bank iD developer portal – https://developer.bankid.cz/docs/apis , https://developer.bankid.cz/docs/high_level_overview_sep
- OpenCV face tutorial (SFace accuracy, thresholds) – https://docs.opencv.org/4.5.4/d0/dd4/tutorial_dnn_face.html
- OpenCV Zoo benchmarks (Raspberry Pi 4 timings) – https://github.com/opencv/opencv_zoo/blob/master/benchmark/README.md
- Anti-spoofing ONNX project – https://github.com/suriAI/face-antispoof-onnx
- Stripe CLI and Checkout fulfilment – https://docs.stripe.com/stripe-cli/use-cli , https://docs.stripe.com/checkout/fulfillment
