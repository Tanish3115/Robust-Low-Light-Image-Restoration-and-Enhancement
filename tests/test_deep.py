import importlib.util
from pathlib import Path

import numpy as np
import pytest

from backend.app.config import Settings
from backend.src.deep.inference import RetinexformerEngine, ModelUnavailable

HAS_TORCH=importlib.util.find_spec('torch') is not None and importlib.util.find_spec('einops') is not None


def test_missing_model_is_never_simulated(tmp_path,dark_rgb):
    engine=RetinexformerEngine(Settings(checkpoint=tmp_path/'missing.pth'))
    assert not engine.status()['available']
    with pytest.raises(ModelUnavailable):engine.enhance(dark_rgb)


def test_overlap_blending_preserves_constant_signal(tmp_path):
    engine=RetinexformerEngine(Settings(checkpoint=tmp_path/'missing.pth',tile_size=64,tile_overlap=16))
    for length in (1,64,65,128,137):
        starts=engine.tile_starts(length,64,16)
        coverage=np.zeros(length)
        for position in starts:coverage[position:position+64]+=1
        assert np.all(coverage>0)
        assert starts==sorted(set(starts))


@pytest.mark.skipif(not HAS_TORCH,reason='Optional torch/einops not installed.')
def test_corrupt_checkpoint_is_rejected(tmp_path):
    path=tmp_path/'bad.pth';path.write_bytes(b'not a checkpoint')
    engine=RetinexformerEngine(Settings(checkpoint=path))
    assert not engine.status()['available']
    assert 'failed' in engine.status()['reason']


@pytest.mark.skipif(not HAS_TORCH,reason='Optional torch/einops not installed.')
def test_official_architecture_state_and_shape(tmp_path):
    # Random official weights validate architecture plumbing only, not restoration quality.
    import torch
    from backend.src.deep.vendor.retinexformer_arch import RetinexFormer
    torch.set_num_threads(2)
    model=RetinexFormer(in_channels=3,out_channels=3,n_feat=40,stage=1,num_blocks=[1,2,2])
    path=tmp_path/'architecture-test-only.pth';torch.save({'params':model.state_dict()},path)
    engine=RetinexformerEngine(Settings(checkpoint=path,device='cpu',tile_size=64,tile_overlap=16))
    result=engine.enhance(np.full((65,71,3),.1,np.float32))
    assert result.image.shape==(65,71,3)
    assert np.isfinite(result.image).all()
    assert result.parameters['tiles']==4
    first_model=engine.model;engine.prepare();assert engine.model is first_model


@pytest.mark.skipif(not HAS_TORCH,reason='Optional torch/einops not installed.')
def test_pretrained_inference_when_checkpoint_is_available(dark_rgb):
    path=Path(__file__).resolve().parents[1]/'checkpoints/LOL_v1.pth'
    if not path.is_file():pytest.skip('Genuine pretrained LOL-v1 checkpoint not provisioned.')
    engine=RetinexformerEngine(Settings(checkpoint=path,device='cpu'))
    result=engine.enhance(dark_rgb)
    assert result.image.shape==dark_rgb.shape
    assert result.latency_ms>0
    assert np.isfinite(result.image).all()
    assert not np.allclose(result.image,dark_rgb)


@pytest.mark.skipif(not HAS_TORCH,reason='Optional torch/einops not installed.')
def test_cuda_request_falls_back_to_cpu_when_unavailable(monkeypatch):
    import torch
    path=Path(__file__).resolve().parents[1]/'checkpoints/LOL_v1.pth'
    if not path.is_file():pytest.skip('Genuine pretrained checkpoint not provisioned.')
    monkeypatch.setattr(torch.cuda,'is_available',lambda:False)
    engine=RetinexformerEngine(Settings(checkpoint=path,device='cuda'))
    assert engine.status()['available']
    assert engine.device=='cpu'


@pytest.mark.skipif(not HAS_TORCH,reason='Optional torch/einops not installed.')
def test_deep_api_is_independent_of_classical_and_fusion(client,png,tmp_path,monkeypatch):
    import backend.app.main as app_module
    import backend.app.service as service_module
    path=Path(__file__).resolve().parents[1]/'checkpoints/LOL_v1.pth'
    if not path.is_file():pytest.skip('Genuine pretrained checkpoint not provisioned.')
    def unexpected(*args,**kwargs):raise AssertionError('Classical pipeline must not run in deep-only mode.')
    monkeypatch.setattr(service_module,'enhance_classical',unexpected)
    monkeypatch.setattr(app_module,'service',service_module.RestorationService(Settings(output_dir=tmp_path/'deep-only',checkpoint=path,device='cpu')))
    response=client.post('/api/enhance',files={'file':('scene.png',png)},data={'mode':'deep'})
    assert response.status_code==200,response.text
    result=response.json()
    assert result['executed_mode']=='deep' and result['controller'] is None
    assert 'classical' not in result['artifacts'] and 'fusion_map' not in result['artifacts']


@pytest.mark.skipif(not HAS_TORCH,reason='Optional torch/einops not installed.')
def test_failed_cuda_initialization_uses_real_cpu_model(monkeypatch):
    import torch
    from backend.src.deep.vendor.retinexformer_arch import RetinexFormer
    path=Path(__file__).resolve().parents[1]/'checkpoints/LOL_v1.pth'
    if not path.is_file():pytest.skip('Pretrained checkpoint not installed.')
    original=RetinexFormer.to
    def transfer(self,device,*args,**kwargs):
        if device=='cuda':raise RuntimeError('Simulated unavailable CUDA driver')
        return original(self,device,*args,**kwargs)
    monkeypatch.setattr(torch.cuda,'is_available',lambda:True);monkeypatch.setattr(RetinexFormer,'to',transfer)
    engine=RetinexformerEngine(Settings(checkpoint=path,device='cuda'))
    assert engine.status()['available'] and engine.device=='cpu'
    assert 'CUDA initialization failed' in engine.status()['warning']


@pytest.mark.skipif(not HAS_TORCH,reason='Optional torch/einops not installed.')
def test_cuda_memory_failure_retries_actual_cpu_inference(monkeypatch,dark_rgb):
    import torch
    path=Path(__file__).resolve().parents[1]/'checkpoints/LOL_v1.pth'
    if not path.is_file():pytest.skip('Pretrained checkpoint not installed.')
    engine=RetinexformerEngine(Settings(checkpoint=path,device='cpu'));engine.prepare();engine.device='cuda'
    original=engine._infer_patch
    def infer(patch):
        if engine.device=='cuda':raise torch.cuda.OutOfMemoryError('Simulated GPU memory failure')
        return original(patch)
    monkeypatch.setattr(engine,'_infer_patch',infer)
    prediction=engine.enhance(dark_rgb)
    assert engine.device=='cpu' and prediction.image.shape==dark_rgb.shape
    assert 'retried' in prediction.parameters['fallback_warning']
