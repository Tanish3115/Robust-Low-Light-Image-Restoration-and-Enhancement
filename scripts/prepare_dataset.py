import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.evaluation.datasets import pair_images, split_manifest


def main():
    parser=argparse.ArgumentParser(description="Prepare a leakage-checked paired or unpaired dataset manifest.")
    parser.add_argument('--train-input',type=Path)
    parser.add_argument('--train-reference',type=Path)
    parser.add_argument('--test-input',type=Path)
    parser.add_argument('--test-reference',type=Path)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--validation-fraction',type=float,default=.1)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--evaluation-only',action='store_true')
    parser.add_argument('--profile',choices=['lol-v1','lol-v2-real','lol-v2-synthetic','dicm','lime','npe','mef','fivek'])
    parser.add_argument('--root',type=Path)
    args=parser.parse_args()
    profile=None
    if args.profile:
        profile=json.loads((Path(__file__).resolve().parents[1]/'configs/datasets.json').read_text())[args.profile]
        if not profile.get('manual_paths'):
            if not args.root:parser.error('--profile requires --root')
            for field in ('train_input','train_reference','test_input','test_reference'):
                if field in profile:setattr(args,field,args.root/profile[field])
            if not profile['paired']:args.evaluation_only=True
    if args.test_reference and not args.test_input:parser.error('--test-reference requires --test-input')
    if not args.evaluation_only and not args.train_input:parser.error('Supply --train-input or choose --evaluation-only.')
    if args.evaluation_only and not args.test_input:parser.error('--evaluation-only requires --test-input.')
    train=pair_images(args.train_input,args.train_reference) if args.train_input else []
    test=pair_images(args.test_input,args.test_reference) if args.test_input else []
    if profile:
        if 'train_count' in profile and len(train)!=profile['train_count']:parser.error('Training count does not match the official dataset profile. Use manual paths for an explicitly labelled subset.')
        if 'test_count' in profile and len(test)!=profile['test_count']:parser.error('Test count does not match the official dataset profile. Use manual paths for an explicitly labelled subset.')
    manifest=split_manifest(train,test,seed=args.seed,validation_fraction=args.validation_fraction) if train else {'version':1,'seed':args.seed,'train':[],'validation':[],'test':test,'protocol':'Evaluation-only dataset; no optimization partition was created.'}
    if args.profile:manifest['dataset']={'name':args.profile,'profile':profile}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print({partition:len(manifest[partition]) for partition in ('train','validation','test')})


if __name__=='__main__':main()
