# FaceGate – progress log

This file says where the project is right now. The design itself is in
[`PLAN.md`](PLAN.md). Update this file after every finished step.

## Step status

Step numbers are the ones from section 7 of `PLAN.md`.

| # | Step | Status |
|---|---|---|
| 0 | Skeleton: folders, READMEs, `.gitignore`, `.env.example` | done 2026-11-11 |
| 1 | `face_core` on Windows: webcam → detect → embedding → match / no match | next |
| 2 | Liveness test on the webcam | |
| – | Speed test of steps 1 and 2 on the Raspberry Pi 3 | |
| 3 | Backend skeleton, PostgreSQL, Alembic, seed, pytest | |
| 4 | `/recognition/identify`, device keys, matching, `gate` with `MockDoor` (Milestone A) | |
| 5 | Second camera from config, visits logic | |
| 6 | Admin API and admin web pages | |
| 7 | Registration with mock BankID and mock payment, live selfie (Milestone B) | |
| 8 | Stripe test mode | |
| 9 | BankID sandbox | |
| 10 | Customer account, fallback code, account deletion | |
| 11 | Statistics pages | |
| 12 | Raspberry Pi: relay on GPIO, keypad, autostart (Milestone C) | |
| 13 | Hardening, final READMEs and tests | |

## Next step: step 1 (short plan, waiting for approval)

Goal: prove the face library choice on Windows before anything else is built.

Files to add:
- `recognition/requirements.txt` – `opencv-python` and `numpy`.
- `recognition/scripts/download_models.py` – downloads the YuNet and SFace
  model files from the OpenCV Zoo into `recognition/face_core/models/` and
  checks their SHA-256 checksum. Model files are not committed.
- `recognition/face_core/detector.py` – finds faces in an image (YuNet),
  returns the largest one.
- `recognition/face_core/embedder.py` – turns a face into a 128-number
  embedding (SFace) and compares two embeddings with cosine similarity.
- `recognition/scripts/demo_match.py` – webcam window: press `e` to enrol the
  face in front of the camera, then it shows the similarity score and
  MATCH / NO MATCH live. The enrolled embedding goes to `recognition/samples/`
  (ignored by git).
- `recognition/tests/` – pytest for the similarity maths (no camera needed).
- `recognition/README.md` – how to install and run.

Not in step 1: liveness, backend, configuration files, the door.

How we check it: models download, tests pass, and in the demo the enrolled
person gets MATCH while another person gets NO MATCH.

## Decisions made

| Date | Decision | Why |
|---|---|---|
| 2026-11-11 | Whole-project plan approved (`PLAN.md`) | |
| 2026-11-11 | Face library: OpenCV YuNet + SFace | One `pip install` on Windows and the Pi, fast enough, free licence. |
| 2026-11-11 | Backend and database run on a PC/laptop, not on the Pi | The Pi 3 has 1 GB RAM; the door program alone fits easily, PostgreSQL + backend on top would be tight. |
| 2026-11-11 | Keep the Raspberry Pi 3 as the door device | See "Hardware" below. |
| 2026-11-11 | Code in `recognition/` stays compatible with Python 3.9 | Keeps the old Bullseye system usable as a fallback. Costs almost nothing: no `match`, no `tomllib`, `from __future__ import annotations` at the top of files. |
| 2026-11-17 | Door camera on the Pi: USB webcam | Plain `cv2.VideoCapture` works the same on Windows and the Pi; no `picamera2` needed. |
| 2026-11-17 | Payment gateway: Stripe test mode | Test account works minutes after sign-up, the payment page is hosted by Stripe (card numbers never touch our server), and the Stripe CLI delivers webhooks to `localhost`. GoPay's sandbox needs credentials requested from GoPay. |

## Hardware

Door device: Raspberry Pi 3, currently Raspbian 11 (Bullseye) 32-bit,
kernel 6.1.21-v7+, armv7l, Python 3.9.

- **The Pi 3 itself is acceptable.** It only detects a face, checks liveness
  and computes one embedding per attempt. The embedding takes about 100 ms on
  a Pi 4 (OpenCV Zoo benchmark). The Pi 3 has not been measured; the estimate
  is 2–4 times slower, so roughly half a second to one second from face to
  decision. This must be measured after step 2.
- **The old system is the weak point, not the board.** Python 3.9 is past its
  end of life and the Bullseye image is no longer offered. On 32-bit ARM some
  libraries have no official packages (for example `onnxruntime`).
- **Plan: install the current 64-bit Raspberry Pi OS** (the Pi 3 has a 64-bit
  processor and is supported). Use a new SD card, or back the old card up
  first, because this erases the old project.
- **Liveness model:** try to run it through OpenCV's own DNN module instead of
  `onnxruntime`, so the Pi needs only one library. Not verified yet; tested in
  step 2.
- **If the Pi fails:** the door program also runs on Windows, so a laptop with
  a webcam can be the door at the defence. The Pi is not a single point of
  failure for the project.

## Open questions for the author

- Can the Pi's SD card be erased, or is a second card needed? The Pi and the
  card are borrowed from the school – the author will ask there first.
- The remaining decisions from section 8 of `PLAN.md`: one-time code or PIN,
  one-time purchase or subscription, Docker or a normal PostgreSQL
  installation.

## Git workflow

One branch per step (`step-0-skeleton`, `step-1-face-core`, …). A branch is
merged into `master` when the author has checked that the step works, so
`master` always holds a working state.

Remote: private repository `RicardoKohlik774/FaceGate` on GitHub (`origin`).
Work happens on two PCs (school and home), so: `git pull` before starting,
commit and `git push` before leaving. Each PC creates its own `.venv`
(`py -3.12 -m venv .venv`); a venv copied from another PC does not work
because it stores that PC's paths.

## Log

- **2026-11-11** – Plan written and approved. Step 0 done: `.gitignore`,
  `.env.example`, root `README.md`, a `README.md` in each of the four part
  folders, `docs/PLAN.md`, this file. `CLAUDE.md` updated: points to `docs/`,
  names YuNet + SFace, notes the Pi 3. Committed on branch `step-0-skeleton`.
- **2026-11-17** – Continued on a second PC (home). Decided: USB webcam on the
  Pi, Stripe test mode. GitHub repository created and connected as `origin`.
  `CLAUDE.md` now lists both PCs. Removed `.claude/settings.json` from the
  repository; `.claude/settings.local.json` is ignored.
