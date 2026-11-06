import importlib.util
from pathlib import Path

import numpy as np
import pytest

from backend.src.evaluation.metrics import evaluate


@pytest.mark.skipif(importlib.util.find_spec('pyiqa') is None,reason='Install requirements-iqa.txt for real IQA integration tests.')
def test_genuine_pretrained_lpips_and_niqe():
    root=Path(__file__).resolve().parents[1]
    if not (root/'checkpoints/metrics/metric-setup.json').is_file():pytest.skip('Run scripts/setup_iqa.py to provision real metric weights.')
    import torch
    torch.set_num_threads(4)
    original=np.random.default_rng(8).uniform(.05,.8,(384,512,3)).astype(np.float32)
    exact=evaluate(original,original,original,enable_iqa=True)
    assert exact['lpips']['available'] and abs(exact['lpips']['value'])<1e-6
    assert exact['niqe']['available'] and np.isfinite(exact['niqe']['value'])
    changed=evaluate(original,np.clip(original*.6,0,1),original,enable_iqa=True)
    assert changed['lpips']['available'] and changed['lpips']['value']>exact['lpips']['value']
