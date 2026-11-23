"""Small helpers shared by the demo scripts."""
from __future__ import annotations

import sys

import cv2
import numpy as np

GREEN = (0, 200, 0)
RED = (0, 0, 230)
YELLOW = (0, 220, 220)


def parse_source(value: str) -> int | str:
    """'0' -> camera number 0, anything else -> video file or network stream."""
    return int(value) if value.isdigit() else value


def open_camera(source: str) -> cv2.VideoCapture:
    parsed = parse_source(source)
    # On Windows, OpenCV's default camera system (MSMF) needs about 40 seconds
    # to open a Logitech Brio 300; DirectShow needs under one. It is only for
    # cameras, not for files and streams, and does not exist on the Pi.
    if isinstance(parsed, int) and sys.platform == "win32":
        return cv2.VideoCapture(parsed, cv2.CAP_DSHOW)
    return cv2.VideoCapture(parsed)


def draw_face(frame: np.ndarray, face: np.ndarray, text: str, color: tuple) -> None:
    x, y, width, height = face[:4].astype(int)
    cv2.rectangle(frame, (x, y), (x + width, y + height), color, 2)
    cv2.putText(frame, text, (x, max(y - 10, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
