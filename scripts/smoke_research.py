"""Verify real ablation, batch, metric, image, and archive API flows over HTTP."""
import argparse
import io
import json
from pathlib import Path
import time
import zipfile

import httpx
from PIL import Image


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8000')
    parser.add_argument('--input',type=Path,required=True);parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('outputs/research-http-verification'))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    low,high=args.input.read_bytes(),args.reference.read_bytes()
    with httpx.Client(base_url=args.url,timeout=240.) as client:
        models=client.get('/api/models');models.raise_for_status()
        assert models.json()['iqa_enabled'] and models.json()['models']['deep']['available']
        response=client.post('/api/ablate',files={'file':('scene.png',low),'reference':('scene.png',high)})
        response.raise_for_status();ablation=response.json()
        assert len(ablation['comparisons'])==9
        for name,candidate in ablation['comparisons'].items():
            for metric in ('psnr','ssim','lpips','niqe'):assert candidate['metrics'][metric]['available'],(name,metric,candidate['metrics'][metric])
            image=client.get(ablation['artifacts'][name]);image.raise_for_status()
            with Image.open(io.BytesIO(image.content)) as decoded:assert list(decoded.size)==ablation['image']['processed_size']
        response=client.post('/api/jobs',files=[('files',('scene.png',low)),('references',('scene.png',high))],data={'ablations':'true'})
        response.raise_for_status();job=response.json();deadline=time.monotonic()+240
        while job['status'] in {'queued','running','cancelling'} and time.monotonic()<deadline:
            time.sleep(.3);response=client.get('/api/jobs/'+job['id']);response.raise_for_status();job=response.json()
        assert job['status']=='completed',job
        assert job['successful']==1 and len(job['report']['per_image'])==9
        archive=client.get(job['download_url']);archive.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(archive.content)) as zipped:
            assert {'report.json','averages.csv','metrics.csv','latency.svg','quality.svg'}<=set(zipped.namelist())
        (args.output/'batch-results.zip').write_bytes(archive.content)
        catalog=client.get('/api/benchmarks');catalog.raise_for_status()
        frontend=client.get('/');frontend.raise_for_status();assert 'LumaRestore AI' in frontend.text
        report={'url':args.url,'ablation_id':ablation['id'],'job':job,'catalog':catalog.json(),
                'checks':{'ablation_variants':9,'all_reference_metrics_available':True,'batch_images':1,'archive':'passed','frontend':'passed'}}
        (args.output/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report['checks'],indent=2))


if __name__=='__main__':main()
