"""Provision genuine pyiqa metric weights locally and run numerical smoke checks."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.app.config import get_settings
from backend.src.evaluation.metrics import _iqa_model,evaluate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable',action='store_true',help='Enable installed metrics in the project .env after successful validation.')
    args=parser.parse_args()
    import torch
    torch.set_num_threads(4)
    for name in ('niqe','lpips'):
        print(f'Provisioning real {name.upper()} weights...',flush=True);_iqa_model(name)
    # Textured, non-constant images exercise NIQE without a fabricated reference score.
    rgb=np.random.default_rng(42).uniform(.05,.8,(384,512,3)).astype(np.float32)
    measured=evaluate(rgb,rgb,rgb,enable_iqa=True)
    if not measured['niqe']['available'] or not measured['lpips']['available']:
        raise SystemExit(json.dumps({name:measured[name] for name in ('niqe','lpips')},indent=2))
    if abs(measured['lpips']['value'])>1e-5:raise SystemExit('Identity LPIPS validation failed.')
    settings=get_settings();cache=settings.absolute(settings.metric_cache_dir);files=[]
    for path in cache.rglob('*'):
        if path.is_file() and path.name!='metric-setup.json':
            with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
            files.append({'path':path.relative_to(cache).as_posix(),'sha256':digest,'bytes':path.stat().st_size})
    report={'implementation':'IQA-PyTorch 0.1.13','checks':{name:measured[name] for name in ('lpips','niqe')},
            'protocol':'Synthetic numerical validation only. Dataset quality claims require real aligned references.', 'files':files}
    (cache/'metric-setup.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    if args.enable:
        env=ROOT/'.env';lines=env.read_text(encoding='utf-8').splitlines() if env.exists() else []
        lines=[line for line in lines if not line.startswith('LUMA_ENABLE_IQA=')];lines.append('LUMA_ENABLE_IQA=true')
        env.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(report['checks'],indent=2))


if __name__=='__main__':main()
