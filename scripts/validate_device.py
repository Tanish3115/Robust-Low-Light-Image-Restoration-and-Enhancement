"""Record actual device support; CUDA is tested only when the hardware exists."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.app.config import Settings
from backend.src.deep.inference import RetinexformerEngine


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'outputs/device-validation.json')
    args=parser.parse_args()
    image=np.random.default_rng(42).uniform(.01,.2,(64,96,3)).astype(np.float32)
    report={'torch':torch.__version__,'cuda_available':torch.cuda.is_available(),'devices':[]}
    cpu=RetinexformerEngine(Settings(device='cpu'));result=cpu.enhance(image)
    report['cpu']={'status':'passed','output_size':list(result.image.shape),'latency_ms':result.latency_ms}
    if torch.cuda.is_available():
        engine=RetinexformerEngine(Settings(device='cuda'));prediction=engine.enhance(image)
        assert engine.device=='cuda' and prediction.image.shape==image.shape and np.isfinite(prediction.image).all()
        report['cuda']={'status':'passed','device':torch.cuda.get_device_name(0),'latency_ms':prediction.latency_ms,
                        'peak_memory_bytes':torch.cuda.max_memory_allocated()}
    else:
        fallback=RetinexformerEngine(Settings(device='cuda'));prediction=fallback.enhance(image)
        assert fallback.device=='cpu' and prediction.image.shape==image.shape
        report['cuda']={'status':'hardware_unavailable','reason':'No NVIDIA CUDA device/runtime is available. Actual CUDA execution cannot be measured on this machine.','cpu_fallback':'passed'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
