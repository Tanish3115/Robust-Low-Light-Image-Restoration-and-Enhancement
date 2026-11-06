import io

import cv2
import numpy as np
from PIL import Image

from backend.src.classical.finish import export_4k, vivid_finish
from backend.src.utils.images import luminance


def test_vivid_brightens_and_increases_muted_colour_without_clipping():
    image = np.tile(np.array([.2, .3, .4], np.float32), (48, 64, 1))
    output = vivid_finish(image)
    assert luminance(output).mean() > luminance(image).mean() * 1.15
    before = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    after = cv2.cvtColor(output, cv2.COLOR_RGB2HSV)
    assert after[:, :, 1].mean() > before[:, :, 1].mean()
    np.testing.assert_allclose(after[:, :, 0], before[:, :, 0], atol=.1)
    assert np.isfinite(output).all() and output.min() >= 0 and output.max() <= 1


def test_vivid_preserves_neutrals_black_and_white():
    image = np.tile(np.linspace(0, 1, 48, dtype=np.float32)[None, :, None], (32, 1, 3))
    original = image.copy()
    output = vivid_finish(image)
    np.testing.assert_array_equal(image, original)
    np.testing.assert_allclose(output[:, :, 0], output[:, :, 1], atol=1e-6)
    np.testing.assert_allclose(output[:, 0], 0, atol=1e-6)
    np.testing.assert_allclose(output[:, -1], 1, atol=1e-6)


def test_portrait_4k_export_preserves_aspect_ratio():
    output = export_4k(np.full((80, 40, 3), .4, np.float32))
    assert output.shape == (3840, 1920, 3)
    np.testing.assert_allclose(output.mean(dtype=np.float64), .4, atol=1e-6)


def test_vivid_api_has_separate_4k_export_and_processing_metrics(client, png):
    result = client.post('/api/enhance', files={'file': ('scene.png', png)},
                         data={'mode': 'classical', 'vivid': 'true', 'upscale_4k': 'true'})
    assert result.status_code == 200, result.text
    data = result.json()
    assert data['parameters']['finish']['preset'] == 'vivid'
    assert 'restored' in data['artifacts']
    exported = Image.open(io.BytesIO(client.get(data['artifacts']['export_4k']).content))
    assert max(exported.size) == 3840
    assert data['parameters']['export_4k']['size'] == list(exported.size)
    assert max(data['image']['processed_size']) < 3840
