# recognition

The door program. Runs on the Raspberry Pi, and on Windows for development.

## What it does

1. Reads frames from one or more cameras.
2. Finds a face and checks that it is a live person (not a photo on a phone).
3. Turns the face into an embedding (a list of 128 numbers).
4. Sends the embedding to the backend and gets back "granted" or "denied".
5. Opens the door (relay on a GPIO pin) when granted.

It does not store any face data and does not decide who may enter. The backend
does that.

## Planned layout

| Path | Purpose |
|---|---|
| `face_core/` | Shared face code: detection, embedding, liveness. Also used by the backend for the registration selfie, so both sides use the same model. |
| `gate/` | The door program: camera loop, door relay, fallback code input, backend client. |
| `scripts/` | Helper scripts, e.g. downloading the model files. |
| `tests/` | Tests. |

## Two cameras, one camera available

Each camera has a direction (entry or exit). A camera source is either a camera
number or a video file, so the missing second camera can be replaced by a video
file or the laptop webcam through configuration.

When not running on a Pi, the door relay is replaced by a mock that only logs
"door opened".

## How to run

Nothing to run yet. Instructions will be added with the first code.
