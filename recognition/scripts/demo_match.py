"""Step 1 demo: enrol your face, then see MATCH / NO MATCH live.

Run from the recognition/ folder:

    python -m scripts.demo_match                       # camera 0
    python -m scripts.demo_match --source 1            # another camera
    python -m scripts.demo_match --source clip.mp4     # a video file
    python -m scripts.demo_match --threshold 0.45      # stricter matching

Keys in the window:  e = enrol the face in front of the camera,  q = quit.

The enrolled embedding is saved to samples/enrolled.npy so it survives a
restart. That file is face data: samples/ is ignored by git and must never
be committed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

from face_core.detector import FaceDetector
from face_core.embedder import FaceEmbedder, cosine_similarity

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
ENROLLED_PATH = SAMPLES_DIR / "enrolled.npy"

# OpenCV suggests 0.363 for SFace. We start a bit stricter (fewer strangers
# accepted, a few more members rejected) and tune it later on real data.
MATCH_THRESHOLD = 0.40

WINDOW_NAME = "FaceGate - step 1 demo"
GREEN = (0, 200, 0)
RED = (0, 0, 230)
YELLOW = (0, 220, 220)


def parse_source(value: str) -> int | str:
    """'0' -> camera number 0, anything else -> path to a video file."""
    return int(value) if value.isdigit() else value


def draw_face(frame: np.ndarray, face: np.ndarray, text: str, color: tuple) -> None:
    x, y, width, height = face[:4].astype(int)
    cv2.rectangle(frame, (x, y), (x + width, y + height), color, 2)
    cv2.putText(frame, text, (x, max(y - 10, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", default="0", help="camera number or video file (default 0)")
    parser.add_argument("--threshold", type=float, default=MATCH_THRESHOLD,
                        help=f"similarity needed for MATCH (default {MATCH_THRESHOLD})")
    args = parser.parse_args()

    detector = FaceDetector()
    embedder = FaceEmbedder()

    enrolled = np.load(ENROLLED_PATH) if ENROLLED_PATH.exists() else None
    if enrolled is not None:
        print(f"Loaded enrolled face from {ENROLLED_PATH}")

    camera = cv2.VideoCapture(parse_source(args.source))
    if not camera.isOpened():
        print(f"Cannot open camera or video: {args.source}")
        return 1

    print("Press 'e' to enrol the face in front of the camera, 'q' to quit.")
    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                print("No more frames (camera disconnected or video ended).")
                break

            face = detector.largest_face(frame)
            embedding = embedder.embed(frame, face) if face is not None else None

            if face is None:
                cv2.putText(frame, "No face", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, YELLOW, 2)
            elif enrolled is None:
                draw_face(frame, face, "Press e to enrol", YELLOW)
            else:
                similarity = cosine_similarity(embedding, enrolled)
                if similarity >= args.threshold:
                    draw_face(frame, face, f"MATCH {similarity:.2f}", GREEN)
                else:
                    draw_face(frame, face, f"NO MATCH {similarity:.2f}", RED)

            cv2.imshow(WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break
            if key == ord("e"):
                if embedding is None:
                    print("No face in the picture, nothing enrolled.")
                else:
                    SAMPLES_DIR.mkdir(exist_ok=True)
                    np.save(ENROLLED_PATH, embedding)
                    enrolled = embedding
                    print(f"Enrolled. Saved to {ENROLLED_PATH}")
            # Closing the window with the X button also ends the demo.
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
