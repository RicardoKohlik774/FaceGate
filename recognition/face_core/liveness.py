"""Guess whether a face is a live person or a photo / screen.

The model is MiniFASNetV2-SE, a small neural network trained on real faces
and on photos and screens that show faces. It looks at texture, screen glare
and edges, so it needs the face together with some of its surroundings.

This is a basic check. It is meant to stop a photo on a phone or on paper,
not a good video on a good screen or a 3D mask.
"""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

MODEL_PATH = Path(__file__).parent / "models" / "minifasnet_v2_se_128.onnx"

# The model must get faces cut out the same way as its authors do it: a
# square 1.5 times bigger than the face box, resized to 128x128.
CROP_SCALE = 1.5
INPUT_SIZE = 128

# A frame counts as real at this score or more. 0.5 is the default of the
# model's authors; tune it on scores from the real door camera.
REAL_THRESHOLD = 0.5

# How many real frames in a row are needed before we believe the person is live.
# A photo on an iPad managed 4 in a row in our test, so 8 is twice that.
REQUIRED_FRAMES = 8

# A face wider than this share of the picture is too close to be judged. An
# iPad photo fooled the model mostly at 25-31 %, so we stay below that.
MAX_FACE_WIDTH = 0.22


def crop_face(image: np.ndarray, face: np.ndarray, scale: float = CROP_SCALE) -> np.ndarray:
    """Cut out a square around the face box, `scale` times its longer side.

    Where the square reaches outside the image, the missing part is filled
    with a mirrored copy of the edge, the same way as the model's authors do.
    """
    x, y, width, height = (float(value) for value in face[:4])
    size = int(max(width, height) * scale)
    left = int(x + width / 2 - size / 2)
    top = int(y + height / 2 - size / 2)
    right, bottom = left + size, top + size

    image_height, image_width = image.shape[:2]
    if left >= image_width or top >= image_height or right <= 0 or bottom <= 0:
        raise ValueError("The face box is outside the image")
    inside = image[max(top, 0):min(bottom, image_height), max(left, 0):min(right, image_width)]

    return cv2.copyMakeBorder(
        inside,
        max(-top, 0), max(bottom - image_height, 0),
        max(-left, 0), max(right - image_width, 0),
        cv2.BORDER_REFLECT_101,
    )


def face_width_share(image: np.ndarray, face: np.ndarray) -> float:
    """Return the face width as a share of the picture width (0.22 = 22 %)."""
    return float(face[2]) / image.shape[1]


def is_too_close(image: np.ndarray, face: np.ndarray) -> bool:
    return face_width_share(image, face) > MAX_FACE_WIDTH


def real_probability(real_output: float, spoof_output: float) -> float:
    """Turn the model's two raw outputs into one score, 0 (spoof) to 1 (real).

    This is softmax for two classes: 1 / (1 + e^(spoof - real)).
    """
    return 1.0 / (1.0 + math.exp(spoof_output - real_output))


class LivenessModel:
    def __init__(self, model_path: Path = MODEL_PATH):
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"Model file not found: {model_path}. "
                "Run 'python -m scripts.download_models' in recognition/ first."
            )
        self._net = cv2.dnn.readNetFromONNX(str(model_path))

    def score(self, image: np.ndarray, face: np.ndarray) -> float:
        """Return how real the face looks, 0 (spoof) to 1 (real)."""
        crop = crop_face(image, face)
        # Same resize methods as the model's authors use.
        enlarging = crop.shape[0] < INPUT_SIZE
        interpolation = cv2.INTER_LANCZOS4 if enlarging else cv2.INTER_AREA
        resized = cv2.resize(crop, (INPUT_SIZE, INPUT_SIZE), interpolation=interpolation)
        # Pixel values 0-255 become 0-1, and OpenCV's BGR becomes RGB.
        blob = cv2.dnn.blobFromImage(resized, scalefactor=1 / 255.0, swapRB=True)
        self._net.setInput(blob)
        real_output, spoof_output = self._net.forward().ravel()
        return real_probability(float(real_output), float(spoof_output))


class LivenessCounter:
    """Says "live" only after enough real frames in a row.

    One lucky frame of a photo is not enough: a single spoof frame, or a frame
    without a usable face, starts the count again from zero.
    """

    def __init__(self, required_frames: int = REQUIRED_FRAMES, threshold: float = REAL_THRESHOLD):
        if required_frames < 1:
            raise ValueError("required_frames must be at least 1")
        self.required_frames = required_frames
        self.threshold = threshold
        self.count = 0

    def update(self, score: float | None) -> bool:
        """Add one frame (None = no face, or too close). Return True when live."""
        if score is not None and score >= self.threshold:
            self.count += 1
        else:
            self.count = 0
        return self.count >= self.required_frames
