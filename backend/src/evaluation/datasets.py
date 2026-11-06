"""Explicit paired/unpaired manifests. Test images are never split or tuned on."""
import hashlib
import json
from pathlib import Path
import random

from PIL import Image

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def image_files(root: Path) -> dict[str, Path]:
    files = {}
    if not root.is_dir():
        raise ValueError(f"Dataset directory does not exist: {root}")
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in EXTENSIONS:
            key = path.relative_to(root).with_suffix("").as_posix().casefold()
            if key in files:
                raise ValueError(f"Ambiguous pairing key: {key}")
            files[key] = path.resolve()
    if not files:
        raise ValueError(f"No supported images found in {root}")
    return files


def pair_images(inputs: Path, references: Path | None) -> list[dict]:
    low = image_files(inputs)
    high = image_files(references) if references else None
    if high is not None and low.keys() != high.keys():
        raise ValueError(f"Pairing mismatch. Missing references: {sorted(low.keys()-high.keys())[:5]}; missing inputs: {sorted(high.keys()-low.keys())[:5]}")
    pairs = []
    for key, path in low.items():
        reference = high[key] if high else None
        with Image.open(path) as image:
            size = image.size
            image.verify()
        if reference:
            with Image.open(reference) as image:
                if image.size != size:
                    raise ValueError(f"Pair has mismatched dimensions: {key}")
                image.verify()
        pairs.append({"key": key, "input": str(path), "reference": str(reference) if reference else None})
    return pairs


def split_manifest(train: list[dict], test: list[dict], *, seed: int = 42, validation_fraction: float = .1) -> dict:
    if not 0 < validation_fraction < 1 or len(train) < 2:
        raise ValueError("At least two training images and a validation fraction between zero and one are required.")
    def hashes(rows):
        fingerprints = set()
        for row in rows:
            for field in ("input", "reference"):
                if row[field]:
                    with Path(row[field]).open("rb") as stream:
                        fingerprints.add(hashlib.file_digest(stream, "sha256").hexdigest())
        return fingerprints
    input_hashes = []
    for row in train:
        with Path(row["input"]).open("rb") as stream:
            input_hashes.append(hashlib.file_digest(stream, "sha256").hexdigest())
    if len(set(input_hashes)) != len(input_hashes):
        raise ValueError("Duplicate training input images could leak across training/validation; remove duplicates first.")
    if test and hashes(train) & hashes(test):
        raise ValueError("Identical image bytes appear in both official train and test partitions; possible leakage.")
    shuffled = list(train)
    random.Random(seed).shuffle(shuffled)
    n = min(len(train)-1, max(1, round(len(train) * validation_fraction)))
    return {"version": 1, "seed": seed, "validation_fraction": validation_fraction,
            "train": shuffled[n:], "validation": shuffled[:n], "test": list(test),
            "protocol": "Validation split only from supplied training partition; official test unchanged. Pair alignment remains the dataset provider's responsibility."}


def read_manifest(path: Path, partition: str) -> list[dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if partition not in {"train", "validation", "test"}:
        raise ValueError("Partition must be train, validation, or test.")
    rows = document[partition]
    if not rows:
        raise ValueError(f"The {partition} partition is empty.")
    return rows
