import numpy as np
import pytest

from backend.src.analysis.analyzer import analyze
from backend.src.classical.pipeline import enhance_classical, select_parameters
from backend.src.utils.images import luminance


def test_dark_scene_gets_brighter_with_real_intermediates(dark_rgb):
    output = enhance_classical(dark_rgb)
    assert luminance(output.image).mean()>luminance(dark_rgb).mean()
    assert output.latency_ms>0
    assert {"reflectance","denoised","clahe","colour_corrected"} <= output.artifacts.keys()
    assert not np.array_equal(output.artifacts["retinex"],output.artifacts["clahe"])
    assert output.image.shape==dark_rgb.shape


@pytest.mark.parametrize("value", [0., .0001, .1, .8, 1.])
@pytest.mark.parametrize("shape", [(1,1,3),(4,5,3),(64,64,3)])
def test_numerical_stability(value,shape):
    rgb=np.full(shape,value,np.float32)
    result=enhance_classical(rgb)
    assert np.isfinite(result.image).all()
    assert result.image.min()>=0 and result.image.max()<=1
    if value==0:assert result.image.max()==0
    if value==1:assert np.allclose(result.image,1)


def test_parameters_adapt_to_degradation(dark_rgb):
    dark=analyze(dark_rgb,maps=False)[0]
    bright=analyze(np.clip(dark_rgb+ .4,0,1),maps=False)[0]
    noisy={**dark,"noise_estimate":.06}
    assert select_parameters(dark)["gamma"]<select_parameters(bright)["gamma"]
    assert select_parameters(noisy)["clahe_clip"]<select_parameters(dark)["clahe_clip"]
    assert select_parameters(noisy)["denoise_mix"]>select_parameters(dark)["denoise_mix"]


def test_highlights_remain_bounded(dark_rgb):
    rgb=dark_rgb.copy();rgb[5:20,5:20]=1
    result=enhance_classical(rgb)
    assert np.allclose(result.image[5:20,5:20],1)
