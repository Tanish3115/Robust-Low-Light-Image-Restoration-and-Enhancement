import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image
import pytest


@pytest.mark.skipif(importlib.util.find_spec('torch') is None or importlib.util.find_spec('einops') is None,
                    reason='Optional neural dependencies not installed.')
def test_one_synthetic_finetuning_step_saves_real_checkpoints(tmp_path):
    root=Path(__file__).resolve().parents[1];checkpoint=root/'checkpoints/LOL_v1.pth'
    if not checkpoint.is_file():pytest.skip('Genuine pretrained checkpoint not provisioned.')
    rows=[]
    for index in range(2):
        low=tmp_path/f'low-{index}.png';high=tmp_path/f'high-{index}.png'
        Image.fromarray(np.full((32,32,3),20+index*10,np.uint8)).save(low)
        Image.fromarray(np.full((32,32,3),80+index*10,np.uint8)).save(high)
        rows.append({'key':str(index),'input':str(low),'reference':str(high)})
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'train':rows[:1],'validation':rows[1:],'test':[]}),encoding='utf-8')
    output=tmp_path/'training'
    result=subprocess.run([sys.executable,str(root/'scripts/finetune.py'),'--manifest',str(manifest),
                           '--checkpoint',str(checkpoint),'--output',str(output),'--epochs','1',
                           '--batch-size','1','--patch-size','16','--device','cpu'],capture_output=True,text=True,timeout=120)
    assert result.returncode==0,result.stdout+result.stderr
    assert (output/'best.pth').is_file() and (output/'last.pth').is_file()
    assert len((output/'training.csv').read_text().splitlines())==2
