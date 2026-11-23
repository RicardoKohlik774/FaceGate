"""Step 2 demo: real face, or a photo / screen?

Run from the recognition/ folder:

    python -m scripts.demo_liveness                    # camera 0
    python -m scripts.demo_liveness --source 1         # another camera
    python -m scripts.demo_liveness --threshold 0.7    # stricter

Every frame shows REAL or SPOOF with the score (0 = spoof, 1 = real). LIVE
appears after enough REAL frames in a row. A face that is too close is shown as
STEP BACK and starts the count again. When you quit, a summary of the
scores is printed, so run the demo once per test (real face, phone photo, ...)
and compare the summaries.

Three numbers are measured; only the width changes what counts as LIVE:
    match   similarity to the face enrolled in demo_match (if there is one)
    width   face width in % of the picture width
    squash  eye-to-mouth height divided by the distance between the eyes; a flat
            photo tilted back should give a smaller number

Keys in the window:  r = clear the scores and start the test again,  q = quit.

Nothing new is saved: no pictures and no face data.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import cv2
import numpy as np

from face_core.detector import FaceDetector
from face_core.embedder import FaceEmbedder, cosine_similarity
from face_core.liveness import (
    MAX_FACE_WIDTH,
    REAL_THRESHOLD,
    REQUIRED_FRAMES,
    LivenessCounter,
    LivenessModel,
    face_width_share,
    is_too_close,
)
from scripts.demo_common import GREEN, RED, YELLOW, draw_face, open_camera
from scripts.demo_match import ENROLLED_PATH, MATCH_THRESHOLD

WINDOW_NAME = "FaceGate - step 2 liveness demo"


@dataclass
class FrameResult:
    score: float
    live: bool
    match: float | None  # None when nobody is enrolled
    width: float
    squash: float
    too_close: bool


def squash_of(face: np.ndarray) -> float:
    """Eye-to-mouth height divided by the distance between the eyes."""
    right_eye, left_eye, _, right_mouth, left_mouth = face[4:14].reshape(5, 2)
    eye_distance = np.linalg.norm(right_eye - left_eye)
    height = np.linalg.norm((right_eye + left_eye) / 2 - (right_mouth + left_mouth) / 2)
    # A head seen fully from the side has almost no eye distance.
    return float(height / max(eye_distance, 1.0))


def print_measurements(name: str, results: list[FrameResult]) -> None:
    """Print the middle value and the usual range (5 % to 95 %) of each number."""
    print(f"{name}: {len(results)} frames")
    if not results:
        return
    for label in ("match", "width", "squash"):
        values = [getattr(result, label) for result in results]
        if None in values:
            continue
        low, middle, high = np.percentile(values, [5, 50, 95])
        print(f"    {label:6}  median {middle:.2f}, usually {low:.2f} to {high:.2f}")


def print_summary(results: list[FrameResult], threshold: float, longest_run: int) -> None:
    if not results:
        print("No face was seen.")
        return
    total = len(results)
    scores = [result.score for result in results]
    real = [result for result in results if result.score >= threshold]
    live = [result for result in results if result.live]
    print(f"Frames with a face: {total}")
    print(f"Score: min {min(scores):.2f}, median {np.median(scores):.2f}, max {max(scores):.2f}")
    print(f"REAL frames: {100 * len(real) / total:.0f} %")
    print(f"LIVE frames: {100 * len(live) / total:.0f} %")
    print(f"Longest run of REAL frames: {longest_run}")
    too_close = sum(result.too_close for result in results)
    print(f"Too close (over {100 * MAX_FACE_WIDTH:.0f} %): {100 * too_close / total:.0f} %")
    if results[0].match is not None:
        matching = [result for result in live if result.match >= MATCH_THRESHOLD]
        print(f"LIVE and MATCH at once: {len(matching)} frames")
    print_measurements("All frames", results)
    print_measurements("LIVE frames", live)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", default="0", help="camera number or video file (default 0)")
    parser.add_argument("--threshold", type=float, default=REAL_THRESHOLD,
                        help=f"score needed for REAL (default {REAL_THRESHOLD})")
    parser.add_argument("--frames", type=int, default=REQUIRED_FRAMES,
                        help=f"REAL frames in a row needed for LIVE (default {REQUIRED_FRAMES})")
    args = parser.parse_args()

    detector = FaceDetector()
    embedder = FaceEmbedder()
    model = LivenessModel()
    enrolled = np.load(ENROLLED_PATH) if ENROLLED_PATH.exists() else None
    if enrolled is None:
        print("Nobody is enrolled, so there is no match score (see demo_match).")
    counter = LivenessCounter(args.frames, args.threshold)

    camera = open_camera(args.source)
    if not camera.isOpened():
        print(f"Cannot open camera or video: {args.source}")
        return 1

    results: list[FrameResult] = []
    longest_run = 0
    print("Press 'r' to clear the scores, 'q' to quit.")
    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                print("No more frames (camera disconnected or video ended).")
                break

            face = detector.largest_face(frame)
            score = model.score(frame, face) if face is not None else None
            too_close = face is not None and is_too_close(frame, face)
            live = counter.update(None if too_close else score)
            longest_run = max(longest_run, counter.count)

            if score is None:
                cv2.putText(frame, "No face", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, YELLOW, 2)
            else:
                match = None
                if enrolled is not None:
                    match = cosine_similarity(embedder.embed(frame, face), enrolled)
                width = 100 * face_width_share(frame, face)
                result = FrameResult(score, live, match, width, squash_of(face), too_close)
                results.append(result)

                text = f"width {width:.0f} %  squash {result.squash:.2f}"
                if match is not None:
                    text = f"match {match:.2f}  " + text
                cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, YELLOW, 2)

                if too_close:
                    draw_face(frame, face, "STEP BACK", RED)
                elif live:
                    draw_face(frame, face, f"LIVE {score:.2f}", GREEN)
                elif score >= args.threshold:
                    draw_face(frame, face, f"REAL {score:.2f} ({counter.count}/{args.frames})", YELLOW)
                else:
                    draw_face(frame, face, f"SPOOF {score:.2f}", RED)

            cv2.imshow(WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break
            if key == ord("r"):
                results.clear()
                longest_run = 0
                counter.count = 0
                print("Scores cleared.")
            # Closing the window with the X button also ends the demo.
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()
    print_summary(results, args.threshold, longest_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
