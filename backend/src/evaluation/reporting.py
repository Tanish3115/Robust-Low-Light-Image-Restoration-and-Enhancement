"""Shared measured report format for CLI benchmarks and web experiments."""
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np


def aggregate(rows: list[dict]) -> dict:
    averages={}
    for mode in sorted({row['mode'] for row in rows}):
        group=[row for row in rows if row['mode']==mode];averages[mode]={}
        for name in group[0]['metrics']:
            values=[row['metrics'][name]['value'] for row in group if row['metrics'][name]['value'] is not None]
            averages[mode][name]={'mean':float(np.mean(values)) if values else None,'count':len(values),
                                 'infinite_count':sum(bool(row['metrics'][name].get('infinite')) for row in group)}
    return averages


def write_report(output: Path, rows: list[dict], *, model: dict, settings: dict,
                 partition='uploaded', ablations=False, unavailable=None, failures=None, manifest=None, dataset=None) -> dict:
    report={'created_at':datetime.now(timezone.utc).isoformat(),'partition':partition,'ablations':ablations,
            'protocol':'Full RGB [0,1], no border crop or reference exposure adjustment. Aligned references required. No test-time optimization.',
            'model':model,'settings':settings,'manifest':manifest,'per_image':rows,'averages':aggregate(rows),
            'unavailable':unavailable or {},'failures':failures or [],
            'dataset':dataset or {'name':'User-uploaded batch' if partition=='uploaded' else 'Custom dataset'},
            'latency_protocol':'Measured method wall time excludes decoding, metrics, disk encoding, and model loading; hybrid includes candidate generation.'}
    output.mkdir(parents=True,exist_ok=True)
    with (output/'metrics.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['image','mode','metric','value','direction','available','reason'])
        for row in rows:
            for name,item in row['metrics'].items():
                writer.writerow([row['key'],row['mode'],name,'infinity' if item.get('infinite') else item['value'],item['direction'],item['available'],item.get('reason')])
    with (output/'averages.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['mode','metric','mean','finite_count','infinite_count'])
        for mode,metrics in report['averages'].items():
            for name,item in metrics.items():writer.writerow([mode,name,item['mean'],item['count'],item['infinite_count']])
    if rows:
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib import pyplot as plt
        modes=list(report['averages']);values=[report['averages'][mode]['latency_ms']['mean'] for mode in modes]
        fig,ax=plt.subplots(figsize=(9,max(3,len(modes)*.4)))
        ax.barh([mode.replace('_',' ') for mode in modes],values,color='#248c96');ax.set_xlabel('Measured mean latency (ms)');ax.invert_yaxis();ax.grid(axis='x',alpha=.2)
        fig.tight_layout();fig.savefig(output/'latency.svg');plt.close(fig)
        supported=[name for name in ('psnr','ssim','lpips','niqe','noise_suppression','edge_preservation')
                   if any(report['averages'][mode].get(name,{}).get('mean') is not None for mode in modes)]
        if supported:
            fig,axes=plt.subplots(len(supported),1,figsize=(10,max(3,3*len(supported))),squeeze=False)
            for ax,name in zip(axes[:,0],supported):
                selected=[mode for mode in modes if report['averages'][mode].get(name,{}).get('mean') is not None]
                ax.bar(selected,[report['averages'][mode][name]['mean'] for mode in selected],color='#248c96')
                ax.set_ylabel(name.replace('_',' '));ax.tick_params(axis='x',rotation=35);ax.grid(axis='y',alpha=.2)
            fig.tight_layout();fig.savefig(output/'quality.svg');plt.close(fig)
    temporary=output/'report.json.tmp';temporary.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8');temporary.replace(output/'report.json')
    return report
