import io
import json

import pytest
from PIL import Image

from backend.app.streamlit_runtime import DemoRuntime, download_checkpoint
from backend.src.deep.inference import ModelUnavailable
from backend.src.utils.images import ImageInputError


def test_demo_classical_has_real_download_and_reference_metrics(tmp_path, png):
    demo = DemoRuntime(tmp_path / 'missing.pth')
    result = demo.run(png, mode='classical', reference_data=png)
    assert Image.open(io.BytesIO(result['enhanced_png'])).size == Image.open(io.BytesIO(png)).size
    report = result['report']
    assert report['executed_mode'] == 'classical'
    assert report['metrics']['ssim']['available']
    assert not report['metrics']['niqe']['available']
    json.dumps(report, allow_nan=False)


def test_demo_auto_fallback_is_explicit_and_deep_never_faked(tmp_path, png):
    demo = DemoRuntime(tmp_path / 'missing.pth')
    result = demo.run(png, allow_download=False)
    assert result['report']['executed_mode'] == 'classical'
    assert any('unavailable' in notice for notice in result['report']['notices'])
    with pytest.raises(ModelUnavailable):
        demo.run(png, mode='deep', allow_download=False)
    assert demo.gate.acquire(blocking=False)
    demo.gate.release()


def test_demo_bounds_inputs_and_rejects_wrong_reference(tmp_path, png):
    demo = DemoRuntime(tmp_path / 'missing.pth')
    with pytest.raises(ImageInputError):
        demo.run(png, max_side=4096)
    reference = io.BytesIO()
    Image.new('RGB', (20, 20)).save(reference, format='PNG')
    with pytest.raises(ImageInputError, match='dimensions'):
        demo.run(png, mode='classical', reference_data=reference.getvalue())
    assert demo.gate.acquire(blocking=False)
    try:
        with pytest.raises(RuntimeError, match='Another image'):
            demo.run(png)
    finally:
        demo.gate.release()


def test_checkpoint_download_rejects_wrong_content_without_installing(tmp_path, monkeypatch):
    class Response(io.BytesIO):
        headers = {'Content-Type': 'application/octet-stream'}
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **kw: Response(b'wrong checkpoint'))
    target = tmp_path / 'LOL_v1.pth'
    with pytest.raises(ModelUnavailable, match='checksum'):
        download_checkpoint(target)
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []
