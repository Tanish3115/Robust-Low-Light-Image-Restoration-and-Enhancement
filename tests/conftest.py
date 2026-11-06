import io
from pathlib import Path
import sys

import numpy as np
from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def dark_rgb():
    rng = np.random.default_rng(7)
    y, x = np.mgrid[:96, :128]
    base = .025 + .14 * x / 128 + .025 * np.sin(y / 4)
    rgb = np.stack([base, base * .85, base * .65], axis=-1)
    rgb += rng.normal(0, .006, rgb.shape)
    rgb[20:40, 70:90] = .9
    return np.clip(rgb, 0, 1).astype(np.float32)


@pytest.fixture
def png(dark_rgb):
    buffer = io.BytesIO()
    Image.fromarray(np.rint(dark_rgb * 255).astype(np.uint8)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    import backend.app.main as module
    from backend.app.config import Settings
    from backend.app.service import RestorationService
    from fastapi.testclient import TestClient
    settings = Settings(output_dir=tmp_path / "results", checkpoint=tmp_path / "missing.pth", max_process_side=128, enable_iqa=False)
    monkeypatch.setattr(module, "service", RestorationService(settings))
    monkeypatch.setattr(module, "settings", settings)
    with TestClient(module.app) as client:
        yield client
