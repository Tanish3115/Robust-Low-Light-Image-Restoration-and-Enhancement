from pathlib import Path
import random

import numpy as np
import torch
from torch.utils.data import Dataset

from backend.src.utils.images import decode_image


class PairedDataset(Dataset):
    def __init__(self, rows: list[dict], *, patch_size=128, augment=True):
        if any(not row['reference'] for row in rows):
            raise ValueError('Supervised fine-tuning requires a reference for every input.')
        self.rows,self.patch_size,self.augment=rows,patch_size,augment

    def __len__(self):return len(self.rows)

    def __getitem__(self,index):
        row=self.rows[index]
        load=lambda path:decode_image(Path(path).read_bytes(),max_pixels=40_000_000,max_side=8192).rgb
        low,high=load(row['input']),load(row['reference'])
        if low.shape!=high.shape:raise ValueError(f"Pair dimension mismatch: {row['key']}")
        patch=self.patch_size
        h,w=low.shape[:2]
        if h<patch or w<patch:
            pad=((0,max(0,patch-h)),(0,max(0,patch-w)),(0,0))
            low=np.pad(low,pad,mode='edge');high=np.pad(high,pad,mode='edge');h,w=low.shape[:2]
        # Validation uses a deterministic central patch, never the official test partition.
        y=random.randint(0,h-patch) if self.augment else (h-patch)//2
        x=random.randint(0,w-patch) if self.augment else (w-patch)//2
        low,high=low[y:y+patch,x:x+patch],high[y:y+patch,x:x+patch]
        if self.augment:
            rotation=random.randrange(4);low=np.rot90(low,rotation);high=np.rot90(high,rotation)
            if random.random()<.5:low=low[:,::-1];high=high[:,::-1]
        tensor=lambda image:torch.from_numpy(np.ascontiguousarray(image.transpose(2,0,1)))
        return tensor(low),tensor(high)
