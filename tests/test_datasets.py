from pathlib import Path
import numpy as np
from PIL import Image
import pytest

from backend.src.evaluation.datasets import pair_images, split_manifest


def test_pairing_split_and_leakage(tmp_path):
    low=tmp_path/'low';high=tmp_path/'high';low.mkdir();high.mkdir()
    for i in range(6):
        Image.fromarray(np.full((8,8,3),i*10,np.uint8)).save(low/f'{i}.png')
        Image.fromarray(np.full((8,8,3),i*10+4,np.uint8)).save(high/f'{i}.png')
    pairs=pair_images(low,high)
    a=split_manifest(pairs,[],seed=9);b=split_manifest(pairs,[],seed=9)
    assert a==b
    assert {r['input'] for r in a['train']}.isdisjoint(r['input'] for r in a['validation'])
    with pytest.raises(ValueError,match='possible leakage'):split_manifest(pairs,pairs[:1])
    (high/'5.png').unlink()
    with pytest.raises(ValueError,match='Pairing mismatch'):pair_images(low,high)


def test_batch_exports_run_actual_modules(tmp_path,monkeypatch):
    import json
    from backend.app.config import Settings
    from scripts import benchmark
    low=tmp_path/'scene.png';Image.fromarray(np.full((32,32,3),20,np.uint8)).save(low)
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps({'test':[{'key':'scene','input':str(low),'reference':None}]}))
    monkeypatch.setattr(benchmark,'get_settings',lambda:Settings(checkpoint=tmp_path/'absent.pth'))
    report=benchmark.run(manifest,tmp_path/'benchmark',ablations=True)
    assert len(report['per_image'])==4
    assert len(report['unavailable'])==5
    assert (tmp_path/'benchmark/metrics.csv').is_file()
    assert (tmp_path/'benchmark/latency.svg').is_file()
    assert (tmp_path/'benchmark/00000/classical.png').is_file()
