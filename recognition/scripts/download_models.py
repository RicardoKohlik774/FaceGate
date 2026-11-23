"""Download the model files: YuNet and SFace (OpenCV Zoo), MiniFASNet (liveness).

The model files are not stored in git (one of them is 38 MB). Run this once
on every machine, from the recognition/ folder:

    python -m scripts.download_models

Each file is checked against its SHA-256 checksum, so a broken or changed
download is never used. The YuNet and SFace checksums are the official ones
published in the OpenCV Zoo repository. For the liveness model we found no
published checksum, so it is of the file we tested on 2026-11-23.
"""
from __future__ import annotations

import hashlib
import os
import sys
import urllib.request
from pathlib import Path

from face_core import detector, embedder, liveness

ZOO_URL = "https://github.com/opencv/opencv_zoo/raw/main/models"
# One fixed commit of facenox/face-antispoof-onnx (formerly suriAI).
ANTISPOOF_URL = (
    "https://raw.githubusercontent.com/facenox/face-antispoof-onnx/"
    "2f8dd93dd0fd9d120f08e83d9020719f67ffdb68"
)

# (where to save it, URL, expected SHA-256)
MODELS = [
    (
        detector.MODEL_PATH,
        ZOO_URL + "/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    ),
    (
        embedder.MODEL_PATH,
        ZOO_URL + "/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    ),
    (
        liveness.MODEL_PATH,
        ANTISPOOF_URL + "/models/best/98.20/best_model.onnx",
        "af2381b88f38769222ed93379e12444e2a50814575de1c46170de570c55a42b6",
    ),
]


def sha256_of(path: Path) -> str:
    """Return the SHA-256 checksum of a file, read in 1 MB pieces."""
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(path: Path, url: str, expected_sha256: str) -> None:
    if path.exists() and sha256_of(path) == expected_sha256:
        print(f"OK (already there): {path.name}")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    # Download to a temporary name first, so an interrupted download
    # never leaves a half-written model file behind.
    part_path = path.with_name(path.name + ".part")
    print(f"Downloading {path.name} ...")
    urllib.request.urlretrieve(url, part_path)

    actual_sha256 = sha256_of(part_path)
    if actual_sha256 != expected_sha256:
        part_path.unlink()
        raise RuntimeError(
            f"Checksum mismatch for {path.name}: expected {expected_sha256}, "
            f"got {actual_sha256}. The file was deleted."
        )
    os.replace(part_path, path)
    print(f"OK (downloaded): {path.name}")


def main() -> int:
    for path, url, expected_sha256 in MODELS:
        download(path, url, expected_sha256)
    return 0


if __name__ == "__main__":
    sys.exit(main())
