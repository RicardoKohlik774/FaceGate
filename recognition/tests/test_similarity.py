"""Tests for the embedding comparison. No camera and no model files needed."""
from __future__ import annotations

import numpy as np
import pytest

from face_core.detector import FaceDetector
from face_core.embedder import EMBEDDING_SIZE, FaceEmbedder, cosine_similarity


def test_same_embedding_gives_one():
    a = np.array([0.3, -1.2, 2.0])
    assert cosine_similarity(a, a) == pytest.approx(1.0)


def test_opposite_embedding_gives_minus_one():
    a = np.array([0.3, -1.2, 2.0])
    assert cosine_similarity(a, -a) == pytest.approx(-1.0)


def test_perpendicular_embeddings_give_zero():
    assert cosine_similarity(np.array([1.0, 0.0]), np.array([0.0, 5.0])) == pytest.approx(0.0)


def test_length_does_not_matter_only_direction():
    a = np.array([0.3, -1.2, 2.0])
    assert cosine_similarity(a, 10 * a) == pytest.approx(1.0)


def test_order_does_not_matter():
    rng = np.random.default_rng(seed=1)
    a, b = rng.normal(size=EMBEDDING_SIZE), rng.normal(size=EMBEDDING_SIZE)
    assert cosine_similarity(a, b) == pytest.approx(cosine_similarity(b, a))


def test_random_embeddings_stay_between_minus_one_and_one():
    rng = np.random.default_rng(seed=2)
    for _ in range(100):
        a, b = rng.normal(size=EMBEDDING_SIZE), rng.normal(size=EMBEDDING_SIZE)
        assert -1.0 <= cosine_similarity(a, b) <= 1.0


def test_shape_from_opencv_is_accepted():
    # OpenCV returns embeddings shaped (1, 128); a saved one is (128,).
    rng = np.random.default_rng(seed=3)
    a = rng.normal(size=EMBEDDING_SIZE)
    assert cosine_similarity(a.reshape(1, -1), a) == pytest.approx(1.0)


def test_different_sizes_are_rejected():
    with pytest.raises(ValueError):
        cosine_similarity(np.ones(128), np.ones(64))


def test_zero_embedding_is_rejected():
    with pytest.raises(ValueError):
        cosine_similarity(np.zeros(128), np.ones(128))


def test_missing_model_file_gives_clear_error(tmp_path):
    missing = tmp_path / "missing.onnx"
    with pytest.raises(FileNotFoundError, match="download_models"):
        FaceDetector(missing)
    with pytest.raises(FileNotFoundError, match="download_models"):
        FaceEmbedder(missing)
