"""Tests for the liveness rules. No camera and no model files needed."""
from __future__ import annotations

import numpy as np
import pytest

from face_core.liveness import LivenessCounter, LivenessModel, crop_face, is_too_close, real_probability


def test_live_only_after_enough_real_frames():
    counter = LivenessCounter(required_frames=3, threshold=0.5)
    assert [counter.update(0.9) for _ in range(4)] == [False, False, True, True]


def test_one_spoof_frame_starts_again():
    counter = LivenessCounter(required_frames=3, threshold=0.5)
    results = [counter.update(score) for score in (0.9, 0.9, 0.1, 0.9, 0.9, 0.9)]
    assert results == [False, False, False, False, False, True]


def test_spoof_frame_ends_live():
    counter = LivenessCounter(required_frames=1, threshold=0.5)
    assert counter.update(0.9)
    assert not counter.update(0.1)


def test_frame_without_a_face_starts_again():
    counter = LivenessCounter(required_frames=2, threshold=0.5)
    results = [counter.update(score) for score in (0.9, None, 0.9, 0.9)]
    assert results == [False, False, False, True]


def test_score_equal_to_threshold_is_real():
    assert LivenessCounter(required_frames=1, threshold=0.5).update(0.5)


def test_zero_required_frames_is_rejected():
    with pytest.raises(ValueError):
        LivenessCounter(required_frames=0)


@pytest.mark.parametrize("width, expected", [(21, False), (22, False), (23, True)])
def test_wide_face_is_too_close(width, expected):
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    assert is_too_close(image, np.array([10, 10, width, 30], dtype=np.float32)) is expected


def test_real_probability():
    assert real_probability(1.0, 1.0) == pytest.approx(0.5)
    assert real_probability(8.0, -8.0) > 0.99
    assert real_probability(-8.0, 8.0) < 0.01


def test_crop_is_a_square_centred_on_the_face():
    image = np.zeros((200, 200, 3), dtype=np.uint8)
    image[100, 100] = 255  # the centre of the face box below
    crop = crop_face(image, np.array([80, 70, 40, 60], dtype=np.float32), scale=1.5)
    assert crop.shape == (90, 90, 3)  # longer side 60 * 1.5
    assert crop[45, 45, 0] == 255


@pytest.mark.parametrize("box", [(-10, -10, 60, 60), (160, 160, 60, 60)])
def test_crop_over_the_image_edge_keeps_its_size(box):
    image = np.zeros((200, 200, 3), dtype=np.uint8)
    crop = crop_face(image, np.array(box, dtype=np.float32), scale=1.5)
    assert crop.shape == (90, 90, 3)


@pytest.mark.parametrize("box", [(900, 100, 20, 20), (100, -900, 20, 20)])
def test_crop_outside_the_image_is_rejected(box):
    image = np.zeros((200, 200, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        crop_face(image, np.array(box, dtype=np.float32))


def test_missing_model_file_gives_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="download_models"):
        LivenessModel(tmp_path / "missing.onnx")
