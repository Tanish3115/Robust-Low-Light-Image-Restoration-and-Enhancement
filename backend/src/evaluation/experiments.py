from backend.src.analysis.analyzer import analyze
from backend.src.classical.pipeline import enhance_classical
from backend.src.hybrid.controller import fuse_adaptive


def run_ablations(rgb, engine):
    """All variants run real modules. Missing neural variants report unavailable."""
    stats=analyze(rgb,maps=False)[0]
    variants={
        'retinex_only':enhance_classical(rgb,stats,denoise=False,clahe=False,colour=False,quality=False),
        'retinex_denoising':enhance_classical(rgb,stats,denoise=True,clahe=False,colour=False,quality=False),
        'retinex_clahe':enhance_classical(rgb,stats,denoise=False,clahe=True,colour=False,quality=False),
        'classical':enhance_classical(rgb,stats),
    }
    missing={}
    if engine.status()['available']:
        deep=engine.enhance(rgb);variants['deep']=deep
        for name,strategy,safeguards in [('fixed_fusion','fixed',False),('global_fusion','global',False),
                                         ('spatial_fusion','spatial',False),('full_hybrid','spatial',True)]:
            variants[name]=fuse_adaptive(rgb,variants['classical'],deep,stats,strategy=strategy,safeguards=safeguards)[0]
    else:
        missing={name:engine.status()['reason'] for name in ('deep','fixed_fusion','global_fusion','spatial_fusion','full_hybrid')}
    return variants,missing
