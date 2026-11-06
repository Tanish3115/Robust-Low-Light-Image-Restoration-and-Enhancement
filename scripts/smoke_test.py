"""Exercise a running backend or the Vite proxy with a generated low-light scene."""
import argparse
import io
import json
from pathlib import Path

import httpx
import numpy as np
from PIL import Image


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8000')
    parser.add_argument('--output',type=Path,default=Path('outputs/smoke'))
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    y,x=np.mgrid[:128,:192]
    scene=np.stack([.03+.13*x/192,.02+.11*x/192,.02+.09*x/192],axis=-1)
    scene[20:55,100:145]=.85
    scene[60:110,25:75]=.16
    scene=np.clip(scene+np.random.default_rng(42).normal(0,.005,scene.shape),0,1)
    buffer=io.BytesIO();Image.fromarray(np.rint(scene*255).astype(np.uint8)).save(buffer,format='PNG')
    data=buffer.getvalue()
    report={}
    with httpx.Client(base_url=args.url,timeout=240.) as client:
        client.get('/health').raise_for_status()
        models=client.get('/api/models');models.raise_for_status();report['models']=models.json()
        for mode in ('classical','deep','hybrid','auto'):
            if not report['models']['models'][mode]['available']:
                report[mode]={'unavailable':report['models']['models'][mode].get('reason')};continue
            response=client.post('/api/enhance',files={'file':('smoke.png',data,'image/png')},data={'mode':mode})
            response.raise_for_status();result=response.json()
            if mode=='deep':
                assert result['controller'] is None and 'classical' not in result['artifacts']
            image=client.get(result['artifacts']['enhanced']);image.raise_for_status()
            assert image.content.startswith(b'\x89PNG')
            (args.output/f'{mode}.png').write_bytes(image.content)
            assert result['image']['processed_size']==[192,128]
            report[mode]={'executed_mode':result['executed_mode'],'latency_ms':result['latency_ms'],'id':result['id']}
            print(f"{mode}: executed={result['executed_mode']} measured={result['latency_ms']:.1f} ms")
        comparison=client.post('/api/compare',files={'file':('smoke.png',data),'reference':('reference.png',data)})
        comparison.raise_for_status();result=comparison.json()
        assert result['comparisons']['classical']['metrics']['psnr']['available']
        exported=client.get(f"/api/results/{result['id']}/metrics");exported.raise_for_status()
        (args.output/'metrics.csv').write_bytes(exported.content)
        report['comparison']=result
    (args.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(f'Live HTTP smoke test passed through {args.url}; synthetic software check only, not a quality benchmark.')


if __name__=='__main__':main()
