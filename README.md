# LumaRestore AI

A local React/TypeScript studio with a FastAPI image-restoration backend. Classical enhancement, genuine pretrained Retinexformer, adaptive hybrid selection/fusion, and automatic mode are implemented. All displayed results come from processing or measured reports.

## Run the application

Tested with Python 3.11 and Node 22. The current project environment, checkpoint, and IQA weights are provisioned.

```powershell
.venv/Scripts/python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd frontend
npm run dev
```

Open http://127.0.0.1:5173. API documentation: http://127.0.0.1:8000/docs. After `npm run build` in frontend, FastAPI also serves the production application at http://127.0.0.1:8000.

## Fresh environment

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -r backend/requirements.txt
Copy-Item .env.example .env
cd frontend
npm ci
npm run build
cd ..
```

Classical mode works without neural dependencies. To add the actual neural and perceptual models:

```powershell
uv pip install --python .venv/Scripts/python.exe -r backend/requirements-deep.txt -r backend/requirements-iqa.txt
.venv/Scripts/python.exe scripts/setup_model.py --download
.venv/Scripts/python.exe scripts/setup_iqa.py --enable
```

The setup script refuses to replace an existing restoration checkpoint. Restart the backend after setup. GPU use requires a CUDA-compatible PyTorch installation and NVIDIA hardware; this machine was verified on CPU. Metric/model assets are cached under checkpoints, with setup provenance. OpenCV and headless OpenCV are pinned to matching 4.11 builds because the IQA dependency tree requires both distributions.

## Application workflows

The six views provide restoration with zoom and before/after comparison, image analysis and spatial maps, pipeline inspection, independent method comparison, benchmark/batch analytics, and regional quality diagnostics. Select an aligned reference to measure PSNR, SSIM and LPIPS; NIQE requires sufficient image size. Missing references or unavailable metrics produce explicit reasons rather than substituted scores.

Analytics supports all nine ablations, asynchronous multi-image jobs, matching reference uploads, progress/cancellation, persisted job history, completed CLI report discovery, image galleries and CSV/JSON/SVG/ZIP exports. Batch limits are 32 images and 100 MB by default. Normal image limits are 20 MB and 40 million input pixels; processing resolution, tiling, retention and device settings are configurable in .env.

The hybrid controller uses local exposure, noise, texture, colour and clipping confidence. It can choose classical, neural or fused output, applies bounded safeguards, and exposes decisions and contribution maps. Artifact maps are heuristic risk indicators, not ground-truth defect labels. Noise/edge proxy metrics are explicitly labelled with their limitations.

## Brighter colours and 4K export

Vivid finish is enabled by default in the studio. It lifts midtones, increases muted colours with gentler treatment of skin-like hues, and applies subtle thresholded sharpening. Neutral black/white anchors and RGB gamut compression limit unwanted colour casts and clipping. Turn it off for the unstyled restoration output.

Select Create 4K export before enhancing to generate an additional PNG with a 3840px long edge, preserving the image aspect ratio. Use Download 4K after processing. This is interpolation, not learned super-resolution, and cannot reconstruct absent detail. Metrics remain on the processing-size enhanced image. API clients can opt in with `vivid=true` and `upscale_4k=true` on `/api/enhance`; comparison, ablation and benchmark outputs stay unchanged.

## Dataset, benchmarking and training

```powershell
.venv/Scripts/python.exe scripts/setup_dataset.py --download
.venv/Scripts/python.exe scripts/benchmark.py --manifest data/LOL-v1/manifest.json --output outputs/new-benchmark --config configs/benchmark.json
.venv/Scripts/python.exe scripts/benchmark.py --manifest data/LOL-v1/manifest.json --output outputs/new-ablations --config configs/benchmark.json --ablations
.venv/Scripts/python.exe scripts/finetune.py --manifest data/LOL-v1/manifest.json --checkpoint checkpoints/LOL_v1.pth --output outputs/new-training --epochs 1 --batch-size 2 --patch-size 64 --device cpu
```

Use new output directories for each run. Dataset preparation validates pairing, partition counts, duplicate/leakage conditions and extraction paths. The official LOL-v1 training partition is split reproducibly into 437 training and 48 development images; the official 15-image test set stays separate. Development images may have been seen during upstream model pretraining. Additional paired/unpaired dataset profiles and manual licensed-data paths are in configs/datasets.json; see `scripts/prepare_dataset.py --help`.

Real official-test comparison (45 rows), nine-variant ablations (135 rows), one actual training epoch, and original/adapted development/test comparisons are saved under outputs. [Measured results](BENCHMARK_RESULTS.md) explain the outcomes: pretrained deep inference beats the current hybrid on LOL-v1, and the degraded adapted checkpoint was not promoted. Training is separate from normal application use.

## API

The OpenAPI page documents request fields. Main endpoints are `/health`, `/api/models`, `/api/analyze`, `/api/enhance`, `/api/compare`, `/api/evaluate`, `/api/ablate`, `/api/jobs`, and `/api/benchmarks`. Jobs expose status, cancellation, artifacts and archive downloads. Completed benchmarks expose reports, artifacts and archives. UUID/path validation, bounded request bodies, bounded processing concurrency and retention protect local resources.

## Verification and Docker

```powershell
.venv/Scripts/python.exe -m pytest -q
cd frontend
npm test -- --run
npm run build
npm audit
cd ..
.venv/Scripts/python.exe scripts/validate_device.py
```

```powershell
docker compose up --build
```

Compose uses the full CPU image, serves the built frontend on port 8000, and mounts project checkpoints read-only. Stop the native backend first if it already uses that port. Provision checkpoint/metric assets before starting Compose. A `classical` Docker build target is also available.

See [verification evidence](VERIFICATION.md) and the [master-prompt implementation audit](TASK_COMPLETION.md). Actual CUDA execution and browser visual inspection remain environment-limited; automated frontend, HTTP, CPU-model, metric, dataset and container checks have run.
