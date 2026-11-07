"""Deploy the complete LumaRestore app after confirming a zero-dollar spend limit.

From the repository root: python -m modal deploy deploy/modal_app.py
This file does not create billing limits; configure them in the Modal dashboard first.
"""
import os
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[1]
if os.environ.get("LUMA_ZERO_SPEND_CONFIRMED") != "1":
    raise RuntimeError(
        "Before deploying, set the Modal workspace spend limit (net charges) to $0, "
        "verify it is saved, and then set LUMA_ZERO_SPEND_CONFIRMED=1. "
        "This flag is an acknowledgement, not a billing control."
    )
for relative in ("checkpoints/LOL_v1.pth", "checkpoints/metrics/metric-setup.json"):
    if not (ROOT / relative).is_file():
        raise RuntimeError(f"Missing {relative}; provision model/IQA assets before deployment.")

image = (
    modal.Image.from_dockerfile(str(ROOT / "Dockerfile"), context_dir=str(ROOT))
    .add_local_dir(str(ROOT / "checkpoints"), "/app/checkpoints", copy=True)
    .env({
        "LUMA_DEVICE": "cpu",
        "LUMA_ENABLE_IQA": "true",
        "LUMA_OUTPUT_DIR": "/data/outputs",
        "LUMA_MAX_PROCESS_SIDE": "1024",
        "LUMA_MAX_BATCH_FILES": "8",
        "LUMA_MAX_RESULTS": "10",
        "LUMA_MAX_UPLOAD_MB": "10",
        "OMP_NUM_THREADS": "2",
        "MKL_NUM_THREADS": "2",
    })
)

app = modal.App("lumarestore")
results = modal.Volume.from_name("lumarestore-results", create_if_missing=True)


@app.function(
    image=image,
    cpu=2,
    memory=4096,
    min_containers=0,
    max_containers=1,
    scaledown_window=60,
    timeout=600,
    volumes={"/data": results},
)
@modal.concurrent(max_inputs=8)
@modal.asgi_app()
def web():
    import sys
    sys.path.insert(0, "/app")
    import torch
    torch.set_num_threads(2)
    from backend.app.main import app as api

    @api.middleware("http")
    async def persist_results(request, call_next):
        response = await call_next(request)
        # Polling requests also persist background-job progress. Modal volumes
        # perform additional background commits during container operation.
        from starlette.concurrency import run_in_threadpool
        await run_in_threadpool(results.commit)
        return response

    return api
