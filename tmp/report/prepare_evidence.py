import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np
from PIL import Image
from backend.src.analysis.analyzer import analyze
from backend.src.classical.pipeline import enhance_classical
from backend.src.utils.images import to_uint8

OUT = ROOT / 'tmp/report'
manifest = json.loads((ROOT / 'data/LOL-v1/manifest.json').read_text())
benchmark = json.loads((ROOT / 'outputs/LOL-v1-final-benchmark/report.json').read_text())
ablation = json.loads((ROOT / 'outputs/LOL-v1-final-ablations/report.json').read_text())
evidence = {'benchmark': benchmark, 'ablation': ablation, 'examples': {}}
for index in [6, 13, 14]:
    row = manifest['test'][index]
    rgb = np.asarray(Image.open(row['input']).convert('RGB'), dtype=np.float32) / 255
    stats, maps = analyze(rgb)
    candidates = {r['mode']: r for r in benchmark['per_image'] if r['key'] == row['key']}
    evidence['examples'][row['key']] = {'index': index, 'stats': stats, 'rows': candidates,
                                      'input': row['input'], 'reference': row['reference']}
    if index == 6:
        result = enhance_classical(rgb, stats)
        for name in ['illumination_original', 'illumination_refined', 'reflectance']:
            Image.fromarray(to_uint8(result.artifacts[name])).save(OUT / f'{name}.png')
        Image.fromarray(to_uint8(maps['edge_map'])).save(OUT / 'edge_map.png')
(OUT / 'evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
print('Prepared measured report data and classical intermediate maps.')
