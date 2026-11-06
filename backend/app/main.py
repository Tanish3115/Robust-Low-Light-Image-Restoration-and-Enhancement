from contextlib import asynccontextmanager
from typing import Annotated
import logging

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import get_settings, ROOT
from backend.app.schemas import Mode, ResultRecord
from backend.app.service import ProcessingBusy, RestorationService
from backend.app.jobs import JobManager
from backend.app.upload_limit import UploadLimitMiddleware
from backend.app.benchmarks import BenchmarkCatalog
from backend.src.utils.images import ImageInputError

settings = get_settings()
service = RestorationService(settings)
logger = logging.getLogger("lumarestore")
jobs: JobManager | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global jobs
    # Load once on startup when configured; failure is visible in /api/models.
    await run_in_threadpool(service.deep.prepare)
    jobs=JobManager(service)
    try:yield
    finally:
        await run_in_threadpool(jobs.close)
        jobs=None


app = FastAPI(title="LumaRestore AI", version="1.0.0", lifespan=lifespan,
              description="Real low-light restoration. Reference metrics are never fabricated.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
app.add_middleware(UploadLimitMiddleware,settings_getter=lambda:settings)


@app.middleware("http")
async def content_limit(request: Request, call_next):
    size = request.headers.get("content-length")
    if size:
        try:
            limit=settings.max_batch_mb*1024**2 if request.url.path=='/api/jobs' else settings.max_upload_mb*1024**2*2
            if int(size) > limit + 262144:
                return JSONResponse(status_code=413, content={"detail": "Request exceeds the upload limit."})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length."})
    return await call_next(request)


@app.exception_handler(ImageInputError)
async def image_error(request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(ProcessingBusy)
async def busy_error(request, exc):
    return JSONResponse(status_code=429, content={"detail": str(exc)}, headers={"Retry-After": "3"})


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    from backend.src.deep.inference import ModelUnavailable
    if isinstance(exc, ModelUnavailable):
        return JSONResponse(status_code=503, content={"detail": str(exc)})
    logger.exception("Restoration request failed")
    return JSONResponse(status_code=500, content={"detail": "Processing failed. Check the backend log for details."})


@app.get("/health")
def health():
    return {"status": "ok", "application": "LumaRestore AI", "version": "1.0.0"}


@app.get("/api/models")
def models():
    return {"models": service.models(), "limits": {"upload_mb": settings.max_upload_mb,
             "input_pixels": settings.max_input_pixels, "process_side": settings.max_process_side},
            "iqa_enabled": settings.enable_iqa}


async def read_upload(file: UploadFile) -> bytes:
    try:
        data = await file.read(settings.max_upload_mb * 1024**2 + 1)
    finally:
        await file.close()
    if len(data) > settings.max_upload_mb * 1024**2:
        raise HTTPException(413, f"Maximum image size is {settings.max_upload_mb} MB.")
    return data


async def execute(file, mode="auto", kind="enhance", strength=1., reference=None, vivid=False, upscale_4k=False):
    data = await read_upload(file)
    reference_data = await read_upload(reference) if reference else None
    from backend.src.deep.inference import ModelUnavailable
    try:
        return await run_in_threadpool(service.process, data, mode=mode, kind=kind,
                                       strength=strength, reference_data=reference_data, vivid=vivid, upscale_4k=upscale_4k)
    except ModelUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/analyze", response_model=ResultRecord)
async def analyze_image(file: Annotated[UploadFile, File()]):
    return await execute(file, kind="analyze")


@app.post("/api/enhance", response_model=ResultRecord)
async def enhance_image(file: Annotated[UploadFile, File()], mode: Annotated[Mode, Form()] = "auto",
                        strength: Annotated[float, Form(ge=.3, le=1.5)] = 1.,
                        vivid: Annotated[bool, Form()] = False, upscale_4k: Annotated[bool, Form()] = False):
    return await execute(file, mode, strength=strength, vivid=vivid, upscale_4k=upscale_4k)


@app.post("/api/compare", response_model=ResultRecord)
async def compare_image(file: Annotated[UploadFile, File()], reference: Annotated[UploadFile | None, File()] = None):
    return await execute(file, "auto", "compare", reference=reference)


@app.post('/api/ablate',response_model=ResultRecord)
async def ablate_image(file: Annotated[UploadFile,File()],reference: Annotated[UploadFile|None,File()]=None):
    return await execute(file,'auto','ablate',reference=reference)


def job_manager() -> JobManager:
    if jobs is None:raise HTTPException(503,'Evaluation worker is not running.')
    return jobs


@app.post('/api/jobs',status_code=202)
async def create_job(files: Annotated[list[UploadFile],File()],
                     references: Annotated[list[UploadFile]|None,File()]=None,
                     ablations: Annotated[bool,Form()]=False):
    references=references or []
    if len(files)>settings.max_batch_files or len(references)>settings.max_batch_files:
        raise HTTPException(422,f'At most {settings.max_batch_files} images per batch.')
    inputs=[];refs=[];total=0
    for uploads,target in ((files,inputs),(references,refs)):
        for upload in uploads:
            name=upload.filename or 'image'
            data=await read_upload(upload);total+=len(data)
            if total>settings.max_batch_mb*1024**2:raise HTTPException(413,'Batch exceeds its total upload limit.')
            target.append((name,data))
    try:return job_manager().submit(inputs,refs,ablations)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc


@app.get('/api/jobs')
def list_jobs():
    manager=job_manager();records=[]
    for path in manager.root.glob('*/job.json'):
        try:
            record=manager.read(path.parent.name)
            records.append({key:record[key] for key in ('id','status','total','completed','successful','ablations','created_at')})
        except KeyError:continue
    return sorted(records,key=lambda item:item['created_at'],reverse=True)


@app.get('/api/jobs/{job_id}')
def read_job(job_id:str):
    try:return job_manager().read(job_id)
    except KeyError as exc:raise HTTPException(404,'Evaluation job not found.') from exc


@app.post('/api/jobs/{job_id}/cancel')
def cancel_job(job_id:str):
    try:return job_manager().cancel(job_id)
    except KeyError as exc:raise HTTPException(404,'Evaluation job not found.') from exc
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc


@app.get('/api/jobs/{job_id}/download')
def download_job(job_id:str):
    manager=job_manager()
    try:
        record=manager.read(job_id);path=manager._path(job_id)/'results.zip'
        if not path.is_file() or not record.get('download_url'):raise HTTPException(409,'Evaluation outputs are not ready.')
        return FileResponse(path,media_type='application/zip',filename=f'lumarestore-{job_id}.zip')
    except KeyError as exc:raise HTTPException(404,'Evaluation job not found.') from exc


@app.get('/api/jobs/{job_id}/artifacts/{name:path}')
def job_artifact(job_id:str,name:str):
    try:
        path=job_manager().artifact(job_id,name)
        return FileResponse(path,filename=path.name,content_disposition_type='inline' if path.suffix in {'.png','.svg'} else 'attachment')
    except KeyError as exc:raise HTTPException(404,'Evaluation artifact not found.') from exc


@app.get('/api/benchmarks')
def list_benchmarks():return BenchmarkCatalog(service.store.root).list()


@app.get('/api/benchmarks/{name}')
def read_benchmark(name:str):
    try:return BenchmarkCatalog(service.store.root).read(name)
    except KeyError as exc:raise HTTPException(404,'Benchmark report not found.') from exc


@app.get('/api/benchmarks/{name}/download')
def download_benchmark(name:str):
    try:return FileResponse(BenchmarkCatalog(service.store.root).archive(name),media_type='application/zip',filename=f'{name}.zip')
    except KeyError as exc:raise HTTPException(404,'Benchmark report not found.') from exc


@app.get('/api/benchmarks/{name}/artifacts/{artifact:path}')
def benchmark_artifact(name:str,artifact:str):
    try:
        path=BenchmarkCatalog(service.store.root).artifact(name,artifact)
        return FileResponse(path,filename=path.name,content_disposition_type='inline' if path.suffix in {'.svg','.png'} else 'attachment')
    except KeyError as exc:raise HTTPException(404,'Benchmark artifact not found.') from exc


@app.post("/api/evaluate", response_model=ResultRecord)
async def evaluate_image(file: Annotated[UploadFile, File()], reference: Annotated[UploadFile | None, File()] = None,
                         mode: Annotated[Mode, Form()] = "classical"):
    return await execute(file, mode, "evaluate", reference=reference)


@app.get("/api/results/{result_id}", response_model=ResultRecord)
def get_result(result_id: str):
    try:
        return service.store.read(result_id)
    except KeyError as exc:
        raise HTTPException(404, "Result not found or expired.") from exc


@app.get("/api/results/{result_id}/{artifact}")
def get_artifact(result_id: str, artifact: str):
    try:
        path, media = service.store.artifact(result_id, artifact)
        if not path.is_file():
            raise KeyError(artifact)
        return FileResponse(path, media_type=media, filename=f"lumarestore-{artifact}{path.suffix}",
                            content_disposition_type="inline" if media == "image/png" else "attachment")
    except KeyError as exc:
        raise HTTPException(404, "Artifact not found or expired.") from exc


# A production build can be served by FastAPI; Vite remains the development server.
if (ROOT / "frontend/dist").is_dir():
    app.mount("/", StaticFiles(directory=ROOT / "frontend/dist", html=True), name="frontend")
