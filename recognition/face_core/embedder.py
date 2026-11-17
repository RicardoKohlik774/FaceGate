"""Turn a face into an embedding with SFace, and compare two embeddings.

An embedding is a list of 128 numbers that describes a face. Photos of the
same person give embeddings that point in almost the same direction; photos
of different people point in different directions. Cosine similarity
measures exactly that, so it is how two faces are compared.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

MODEL_PATH = Path(__file__).parent / "models" / "face_recognition_sface_2021dec.onnx"

# Stored next to every embedding later: embeddings from different models
# cannot be compared with each other.
MODEL_NAME = "sface_2021dec"

EMBEDDING_SIZE = 128


class FaceEmbedder:
    def __init__(self, model_path: Path = MODEL_PATH):
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"Model file not found: {model_path}. "
                "Run 'python -m scripts.download_models' in recognition/ first."
            )
        self._recognizer = cv2.FaceRecognizerSF.create(str(model_path), "")

    def embed(self, image: np.ndarray, face: np.ndarray) -> np.ndarray:
        """Return the 128-number embedding of one face found by FaceDetector.

        alignCrop uses the five face points to rotate and cut the face to the
        112x112 picture SFace was trained on, so a tilted head still gives a
        similar embedding.
        """
        aligned_face = self._recognizer.alignCrop(image, face)
        feature = self._recognizer.feature(aligned_face)
        return feature.flatten().astype(np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Return the cosine of the angle between two embeddings.

    1 = same direction (same face), 0 = unrelated, -1 = opposite.
    Formula: (a . b) / (|a| * |b|)
    """
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    if a.shape != b.shape:
        raise ValueError(f"Embeddings have different sizes: {a.shape} and {b.shape}")
    norm_product = np.linalg.norm(a) * np.linalg.norm(b)
    if norm_product == 0:
        raise ValueError("An embedding of all zeros has no direction")
    return float(np.dot(a, b) / norm_product)
