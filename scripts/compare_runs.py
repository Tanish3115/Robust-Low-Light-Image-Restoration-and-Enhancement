"""Compare measured paired reports without changing any application checkpoint."""
import argparse
import csv
import json
from pathlib import Path
import os
os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parents[1]/'.cache/matplotlib'))


def compare(baseline:Path,candidate:Path,output:Path,mode='deep'):
    before=json.loads(baseline.read_text(encoding='utf-8'));after=json.loads(candidate.read_text(encoding='utf-8'))
    left={row['key']:row for row in before['per_image'] if row['mode']==mode}
    right={row['key']:row for row in after['per_image'] if row['mode']==mode}
    if not left or left.keys()!=right.keys() or before['partition']!=after['partition']:raise ValueError('Reports must contain the same images, mode, and partition.')
    if output.exists() and any(output.iterdir()):raise ValueError('Use an empty comparison output directory.')
    output.mkdir(parents=True,exist_ok=True)
    metrics={}
    for name in ('psnr','ssim','lpips','niqe','edge_preservation','noise_suppression'):
        pairs=[(left[key]['metrics'][name]['value'],right[key]['metrics'][name]['value']) for key in left
               if left[key]['metrics'][name]['value'] is not None and right[key]['metrics'][name]['value'] is not None]
        if not pairs:continue
        first=sum(pair[0] for pair in pairs)/len(pairs);second=sum(pair[1] for pair in pairs)/len(pairs)
        direction=next(iter(left.values()))['metrics'][name]['direction']
        metrics[name]={'baseline':first,'candidate':second,'delta':second-first,'direction':direction,'paired_count':len(pairs)}
    report={'mode':mode,'partition':before['partition'],'images':len(left),'metrics':metrics,
            'baseline_checkpoint':before['model'].get('checkpoint_sha256'),'candidate_checkpoint':after['model'].get('checkpoint_sha256'),
            'checkpoint_replaced':False,'protocol':'Paired comparison only; no parameters or checkpoints are changed. A development split taken from a pretrained model training set is not an independent unseen evaluation.'}
    (output/'comparison.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    with (output/'comparison.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['metric','baseline','candidate','delta','direction','paired_images'])
        for name,item in metrics.items():writer.writerow([name,item['baseline'],item['candidate'],item['delta'],item['direction'],item['paired_count']])
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    names=[name for name in ('psnr','ssim','lpips','niqe') if name in metrics]
    fig,axes=plt.subplots(1,len(names),figsize=(4*len(names),4),squeeze=False)
    for ax,name in zip(axes[0],names):
        ax.bar(['Pretrained','Adapted'],[metrics[name]['baseline'],metrics[name]['candidate']],color=['#248c96','#6962af']);ax.set_title(name.upper());ax.grid(axis='y',alpha=.2)
    fig.tight_layout();fig.savefig(output/'adaptation.svg');plt.close(fig)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True);parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--mode',default='deep')
    args=parser.parse_args();print(json.dumps(compare(args.baseline,args.candidate,args.output,args.mode),indent=2))
