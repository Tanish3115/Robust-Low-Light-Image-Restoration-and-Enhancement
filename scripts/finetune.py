"""Optional supervised fine-tuning; requires paired train/validation data and pretrained weights."""
import argparse
import csv
import json
from pathlib import Path
import random
import sys

import numpy as np
import torch
import torch.nn.functional as functional
from torch.utils.data import DataLoader

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.config import Settings
from backend.src.deep.inference import RetinexformerEngine
from backend.src.evaluation.datasets import read_manifest
from backend.src.training.dataset import PairedDataset


def restoration_loss(prediction,reference):
    charbonnier=torch.sqrt((prediction-reference).square()+1e-6).mean()
    edge_x=functional.l1_loss(prediction[:,:,:,1:]-prediction[:,:,:,:-1],reference[:,:,:,1:]-reference[:,:,:,:-1])
    edge_y=functional.l1_loss(prediction[:,:,1:,:]-prediction[:,:,:-1,:],reference[:,:,1:,:]-reference[:,:,:-1,:])
    return charbonnier+.05*(edge_x+edge_y)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True,type=Path);parser.add_argument('--checkpoint',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path);parser.add_argument('--epochs',type=int,default=50)
    parser.add_argument('--batch-size',type=int,default=4);parser.add_argument('--patch-size',type=int,default=128)
    parser.add_argument('--learning-rate',type=float,default=3e-4);parser.add_argument('--patience',type=int,default=5)
    parser.add_argument('--seed',type=int,default=42);parser.add_argument('--device',choices=['auto','cpu','cuda'],default='auto')
    args=parser.parse_args()
    if args.patch_size<16 or args.patch_size%8:parser.error('Patch size must be a multiple of 8, at least 16.')
    if min(args.epochs,args.batch_size,args.patience)<=0:parser.error('Epochs, batch size, and patience must be positive.')
    if args.output.exists() and any(args.output.iterdir()):parser.error('Use an empty output directory.')
    random.seed(args.seed);np.random.seed(args.seed);torch.manual_seed(args.seed)
    train_rows=read_manifest(args.manifest,'train');validation_rows=read_manifest(args.manifest,'validation')
    train_paths={str(Path(row['input']).resolve()) for row in train_rows}
    if train_paths & {str(Path(row['input']).resolve()) for row in validation_rows}:parser.error('Training and validation overlap.')
    engine=RetinexformerEngine(Settings(checkpoint=args.checkpoint.resolve(),device=args.device));engine.prepare()
    if engine.model is None:raise SystemExit(engine.reason)
    model=engine.model;device=engine.device
    train=DataLoader(PairedDataset(train_rows,patch_size=args.patch_size),batch_size=args.batch_size,shuffle=True,num_workers=0)
    validation=DataLoader(PairedDataset(validation_rows,patch_size=args.patch_size,augment=False),batch_size=1,num_workers=0)
    optimizer=torch.optim.Adam(model.parameters(),lr=args.learning_rate,betas=(.9,.999))
    schedule=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=args.epochs,eta_min=1e-6)
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'config.json').write_text(json.dumps({**vars(args),'manifest':str(args.manifest),'checkpoint':str(args.checkpoint),'output':str(args.output),'device_actual':device,'protocol':'Charbonnier + .05 gradient L1; central-patch validation; optional fine-tuning, not a reproduction of official training.'},indent=2),encoding='utf-8')
    best=float('inf');stale=0
    with (args.output/'training.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.writer(stream);writer.writerow(['epoch','train_loss','validation_loss','learning_rate'])
        for epoch in range(args.epochs):
            model.train();train_loss=0
            for low,high in train:
                low,high=low.to(device),high.to(device);optimizer.zero_grad(set_to_none=True)
                loss=restoration_loss(model(low),high)
                if not torch.isfinite(loss):raise RuntimeError('Non-finite training loss; training stopped.')
                loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step();train_loss+=loss.item()
            model.eval();validation_loss=0
            with torch.inference_mode():
                for low,high in validation:validation_loss+=restoration_loss(model(low.to(device)),high.to(device)).item()
            train_loss/=len(train);validation_loss/=len(validation)
            writer.writerow([epoch+1,train_loss,validation_loss,optimizer.param_groups[0]['lr']]);stream.flush()
            payload={'params':model.state_dict(),'optimizer':optimizer.state_dict(),'epoch':epoch+1,'validation_loss':validation_loss}
            torch.save(payload,args.output/'last.pth')
            if validation_loss<best:
                best=validation_loss;stale=0;torch.save({'params':model.state_dict()},args.output/'best.pth')
            else:stale+=1
            print(f'Epoch {epoch+1}: train={train_loss:.5f} validation={validation_loss:.5f}')
            schedule.step()
            if stale>=args.patience:print('Early stopping.');break


if __name__=='__main__':main()
