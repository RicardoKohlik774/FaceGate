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

## Layout

| Path | Purpose |
|---|---|
| `face_core/detector.py` | Finds faces in an image (YuNet). Returns the box, five face points and a score for each face. |
| `face_core/embedder.py` | Turns a face into an embedding of 128 numbers (SFace) and compares two embeddings with cosine similarity. |
| `face_core/models/` | The `.onnx` model files. Downloaded by a script, not stored in git. |
| `scripts/download_models.py` | Downloads both model files and checks their SHA-256 checksums. |
| `scripts/demo_match.py` | Webcam demo: enrol your face, then see MATCH / NO MATCH live. |
| `tests/` | pytest tests (no camera or model files needed). |
| `gate/` | Planned: the door program (camera loop, door relay, fallback code, backend client). |

`face_core` will also be used by the backend for the registration selfie, so
the selfie and the door camera always use exactly the same models.

## Two cameras, one camera available

Each camera has a direction (entry or exit). A camera source is either a camera
number or a video file, so the missing second camera can be replaced by a video
file or the laptop webcam through configuration.

When not running on a Pi, the door relay is replaced by a mock that only logs
"door opened".

## How to run

All commands are run from this `recognition/` folder with the project's
virtual environment active (`..\.venv\Scripts\activate` on Windows).

```
pip install -r requirements.txt
python -m scripts.download_models     # once per machine
python -m pytest                      # tests
python -m scripts.demo_match          # webcam demo
```

Scripts are started with `python -m scripts.<name>` (not `python scripts\<name>.py`)
so that Python finds the `face_core` package in this folder.

In the demo window: `e` enrols the face in front of the camera, `q` quits.
Options: `--source 1` for another camera, `--source clip.mp4` for a video
file, `--threshold 0.45` for stricter matching. The enrolled face is saved to
`samples/enrolled.npy`; `samples/` is ignored by git because it contains face
data.

## How a match is decided

Cosine similarity of two embeddings: 1 means the same direction (same face),
0 means unrelated. The demo says MATCH at 0.40 or more. OpenCV suggests 0.363
for SFace; we start a bit stricter and tune the value later on real data.
