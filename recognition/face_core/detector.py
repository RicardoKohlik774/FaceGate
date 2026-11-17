"""Find faces in an image with YuNet, OpenCV's built-in face detector.

For every face YuNet returns one row of 15 numbers:
    [0:4]   x, y, width, height of the face box (pixels)
    [4:14]  five face points as (x, y) pairs: right eye, left eye,
            nose tip, right mouth corner, left mouth corner
    [14]    confidence score, 0 to 1

The embedder needs the whole row: it uses the five points to straighten
the face before turning it into numbers.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

MODEL_PATH = Path(__file__).parent / "models" / "face_detection_yunet_2023mar.onnx"

# Faces with a lower confidence are ignored. 0.9 is the value used in
# OpenCV's own face detection sample.
SCORE_THRESHOLD = 0.9


class FaceDetector:
    def __init__(self, model_path: Path = MODEL_PATH, score_threshold: float = SCORE_THRESHOLD):
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"Model file not found: {model_path}. "
                "Run 'python -m scripts.download_models' in recognition/ first."
            )
        # The input size given here is a placeholder; detect() sets the real
        # size of each image before detecting.
        self._detector = cv2.FaceDetectorYN.create(
            str(model_path), "", (320, 320), score_threshold
        )

    def detect(self, image: np.ndarray) -> np.ndarray:
        """Return all faces in a BGR image as an array of shape (N, 15)."""
        height, width = image.shape[:2]
        self._detector.setInputSize((width, height))
        _, faces = self._detector.detect(image)
        if faces is None:
            return np.empty((0, 15), dtype=np.float32)
        return faces

    def largest_face(self, image: np.ndarray) -> np.ndarray | None:
        """Return the biggest face (the person closest to the camera), or None."""
        faces = self.detect(image)
        if len(faces) == 0:
            return None
        return max(faces, key=lambda face: face[2] * face[3])
