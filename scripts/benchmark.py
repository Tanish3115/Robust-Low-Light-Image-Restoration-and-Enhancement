"""Offline benchmark and ablation runner; references never influence restoration."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import perf_counter

import numpy as np
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.config import get_settings
from backend.src.classical.pipeline import enhance_classical
from backend.src.deep.inference import RetinexformerEngine
from backend.src.evaluation.datasets import read_manifest
from backend.src.evaluation.experiments import run_ablations
from backend.src.evaluation.metrics import evaluate,diagnostics
from backend.src.hybrid.controller import fuse_adaptive
from backend.src.analysis.analyzer import analyze
from backend.src.utils.images import decode_image, to_uint8


def run(manifest: Path, output: Path, *, partition='test', ablations=False, enable_iqa=False, config:Path|None=None, modes:list[str]|None=None):
    settings=get_settings()
    if config:
        from backend.app.config import Settings
        overrides=json.loads(config.read_text(encoding='utf-8'))
        if not isinstance(overrides,dict) or overrides.keys()-Settings.model_fields.keys():raise ValueError('Benchmark configuration contains unknown settings.')
        settings=Settings(**{**settings.model_dump(),**overrides})
    engine=RetinexformerEngine(settings)
    rows=read_manifest(manifest,partition)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Benchmark output directory must be empty to avoid mixing runs.')
    output.mkdir(parents=True,exist_ok=True)
    measurements=[];unavailable={}
    for index,row in enumerate(rows):
        decode=lambda path:decode_image(Path(path).read_bytes(),max_pixels=settings.max_input_pixels,max_side=settings.max_process_side)
        decoded=decode(row['input']);rgb=decoded.rgb
        reference=decode(row['reference']) if row['reference'] else None
        if reference and (reference.original_size!=decoded.original_size or reference.rgb.shape!=rgb.shape):
            raise ValueError(f"Reference shape mismatch: {row['key']}")
        if ablations:
            candidates,missing=run_ablations(rgb,engine);unavailable.update(missing)
        else:
            stats=analyze(rgb,maps=False)[0]
            classical=enhance_classical(rgb,stats);candidates={'classical':classical}
            if engine.status()['available']:
                deep=engine.enhance(rgb)
                candidates['deep']=deep;candidates['hybrid']=fuse_adaptive(rgb,classical,deep,stats)[0]
            else:unavailable.update(deep=engine.status()['reason'],hybrid=engine.status()['reason'])
        if modes:candidates={name:value for name,value in candidates.items() if name in modes}
        folder=output/f'{index:05d}';folder.mkdir()
        Image.fromarray(to_uint8(rgb)).save(folder/'original.png')
        for name,candidate in candidates.items():
            metrics=evaluate(rgb,candidate.image,reference.rgb if reference else None,
                             latency_ms=candidate.latency_ms,enable_iqa=enable_iqa)
            Image.fromarray(to_uint8(candidate.image)).save(folder/f'{name}.png')
            measurements.append({'key':row['key'],'mode':name,'metrics':metrics,'parameters':candidate.parameters,
                                 'diagnostics':diagnostics(rgb,candidate.image),
                                 'processed_size':list(decoded.processed_size),'resized':decoded.resized})
        print(f"[{index+1}/{len(rows)}] {row['key']}: {', '.join(candidates)}")
    from backend.src.evaluation.reporting import write_report
    return write_report(output,measurements,model=engine.status(),settings=settings.model_dump(mode='json'),
                        partition=partition,ablations=ablations,unavailable=unavailable,manifest=str(manifest.resolve()),
                        dataset=json.loads(manifest.read_text(encoding='utf-8')).get('dataset'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--partition',choices=['train','validation','test'],default='test')
    parser.add_argument('--ablations',action='store_true');parser.add_argument('--iqa',action='store_true')
    parser.add_argument('--config',type=Path)
    parser.add_argument('--modes',nargs='+',choices=['classical','deep','hybrid'])
    args=parser.parse_args();start=perf_counter()
    if args.ablations and args.modes:parser.error('--modes applies to comparison runs; ablations execute the complete configured study.')
    run(args.manifest,args.output,partition=args.partition,ablations=args.ablations,enable_iqa=args.iqa,config=args.config,modes=args.modes)
    print(f'Report and outputs saved to {args.output} in {perf_counter()-start:.2f}s')
