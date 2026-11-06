import numpy as np
import pytest
from backend.src.analysis.analyzer import analyze
from backend.src.classical.pipeline import PipelineResult, enhance_classical
from backend.src.evaluation.metrics import evaluate
from backend.src.hybrid.controller import fuse_adaptive


def test_reference_metrics_have_known_values(dark_rgb):
    exact=evaluate(dark_rgb,dark_rgb,dark_rgb)
    assert exact['psnr']['infinite']
    assert abs(exact['ssim']['value']-1)<1e-6
    black=np.zeros((32,32,3),np.float32)
    metrics=evaluate(black,black,np.full_like(black,.1))
    assert abs(metrics['psnr']['value']-20)<1e-4
    assert not evaluate(black,black)['psnr']['available']
    assert evaluate(black,black)['noise_suppression']['value'] is None


def test_fusion_is_spatial_and_rejects_bad_candidate(dark_rgb):
    stats=analyze(dark_rgb,maps=False)[0]
    classical=enhance_classical(dark_rgb,stats)
    # Deliberately bad candidate: numerical controller test, not neural inference.
    candidate=np.clip(dark_rgb*2,0,1);candidate[:,:64]=1
    deep=PipelineResult(candidate,{}, {}, 2.)
    result,decision=fuse_adaptive(dark_rgb,classical,deep,stats)
    weights=result.artifacts['fusion_raw']
    assert 0<=weights.min()<=weights.max()<=1
    assert weights.std()>.01
    assert weights[:,:50].mean()<weights[:,80:].mean()
    assert result.image.shape==dark_rgb.shape
    assert abs(decision['classical_contribution']+decision['deep_contribution']-1)<1e-6


def test_ablation_strategies_are_distinct(dark_rgb):
    stats=analyze(dark_rgb,maps=False)[0];c=enhance_classical(dark_rgb)
    d=PipelineResult(np.clip(dark_rgb*2,0,1),{}, {},1)
    fixed,_=fuse_adaptive(dark_rgb,c,d,stats,strategy='fixed',safeguards=False)
    global_,_=fuse_adaptive(dark_rgb,c,d,stats,strategy='global',safeguards=False)
    assert np.allclose(fixed.artifacts['fusion_map'],.5)
    assert global_.artifacts['fusion_map'].std()<1e-6
    assert not np.allclose(fixed.image,global_.image)


def test_optional_iqa_failures_are_independent(monkeypatch,dark_rgb):
    torch=pytest.importorskip('torch')
    import backend.src.evaluation.metrics as module
    def load(name):
        if name=='niqe':raise RuntimeError('Metric weights unavailable')
        return lambda *args:torch.tensor(.123)
    monkeypatch.setattr(module,'_iqa_model',load)
    metrics=evaluate(dark_rgb,dark_rgb,dark_rgb,enable_iqa=True)
    assert not metrics['niqe']['available']
    assert metrics['lpips']['value']==pytest.approx(.123)


def test_small_reference_iqa_reports_the_actual_limit():
    pytest.importorskip('torch')
    image=np.zeros((32,32,3),np.float32)
    metrics=evaluate(image,image,image,enable_iqa=True)
    assert '64×64' in metrics['lpips']['reason']
    assert '192×192' in metrics['niqe']['reason']


def test_mild_scene_can_select_classical_instead_of_fusion():
    original=np.full((64,64,3),.4,np.float32)
    stats=analyze(original,maps=False)[0]
    classical=enhance_classical(original,stats)
    deep=PipelineResult(classical.image.copy(),{}, {},1.)
    result,decision=fuse_adaptive(original,classical,deep,stats)
    assert decision['selected_mode']=='classical'
    assert decision['deep_contribution']==0
    assert np.array_equal(result.image,classical.image)


def test_controller_can_select_deep_instead_of_assuming_fusion_is_superior():
    original=np.full((64,64,3),.1,np.float32);stats=analyze(original,maps=False)[0]
    classical=PipelineResult(np.full_like(original,.2),{}, {},1)
    deep=PipelineResult(np.full_like(original,.4),{}, {},1)
    result,decision=fuse_adaptive(original,classical,deep,stats)
    assert decision['selected_mode']=='deep'
    assert decision['deep_contribution']==1 and np.array_equal(result.image,deep.image)
