"""Bounded local background evaluation jobs, progress, cancellation, and downloads."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import shutil
import threading
import uuid
import zipfile

from PIL import Image

from backend.app.storage import VALID_ID
from backend.app.service import ProcessingBusy
from backend.src.analysis.analyzer import analyze
from backend.src.classical.pipeline import enhance_classical
from backend.src.evaluation.experiments import run_ablations
from backend.src.evaluation.metrics import diagnostics,evaluate
from backend.src.evaluation.reporting import write_report
from backend.src.hybrid.controller import fuse_adaptive
from backend.src.utils.images import ImageInputError,to_uint8

logger=logging.getLogger('lumarestore.jobs')


class JobManager:
    def __init__(self,service):
        self.service=service;self.root=service.store.root/'jobs';self.root.mkdir(exist_ok=True)
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='luma-evaluation')
        self.lock=threading.RLock();self.slots=threading.BoundedSemaphore(3);self.cancelled={}
        for path in self.root.glob('*/job.json'):
            if not VALID_ID.fullmatch(path.parent.name) or path.parent.is_symlink():continue
            try:
                record=json.loads(path.read_text(encoding='utf-8'))
                if record['status'] in {'queued','running','cancelling'}:
                    record.update(status='interrupted',error='Backend restarted before completion. Resubmit the input files.')
                    self._write(path.parent,record)
            except (OSError,ValueError,KeyError):continue

    def _path(self,job_id):
        if not VALID_ID.fullmatch(job_id):raise KeyError('Unknown job')
        path=self.root/job_id
        if path.is_symlink() or path.resolve().parent!=self.root.resolve():raise KeyError('Unknown job')
        return path

    def _write(self,path,record):
        temporary=path/'job.json.tmp';temporary.write_text(json.dumps(record,allow_nan=False),encoding='utf-8');temporary.replace(path/'job.json')

    def _update(self,job_id,**values):
        with self.lock:
            path=self._path(job_id);record=json.loads((path/'job.json').read_text(encoding='utf-8'));record.update(values);self._write(path,record)

    def submit(self,inputs:list[tuple[str,bytes]],references:list[tuple[str,bytes]],ablations:bool):
        if not self.slots.acquire(blocking=False):raise ProcessingBusy('The evaluation queue is full (three jobs). Wait for a job to finish.')
        job_id=uuid.uuid4().hex;path=self._path(job_id)
        try:
            self.cleanup();path.mkdir();(path/'inputs').mkdir()
            key=lambda name:Path(name.replace('\\','/')).stem.casefold()
            reference_map={key(name):data for name,data in references}
            if len(reference_map)!=len(references):raise ImageInputError('Reference filenames have duplicate stems.')
            if len({key(name) for name,_ in inputs})!=len(inputs):raise ImageInputError('Input filenames have duplicate stems.')
            if references and set(reference_map)!={key(name) for name,_ in inputs}:raise ImageInputError('Reference stems must match every input stem exactly.')
            rows=[]
            for index,(name,data) in enumerate(inputs):
                low=path/'inputs'/f'{index:05d}.input';low.write_bytes(data)
                high=None
                if reference_map:
                    high=path/'inputs'/f'{index:05d}.reference';high.write_bytes(reference_map[key(name)])
                rows.append({'key':Path(name.replace('\\','/')).name,'input':str(low),'reference':str(high) if high else None})
            (path/'inputs.json').write_text(json.dumps(rows),encoding='utf-8')
            record={'id':job_id,'status':'queued','total':len(rows),'completed':0,'successful':0,'ablations':ablations,
                    'created_at':datetime.now(timezone.utc).isoformat(),'failures':[],'error':None}
            self._write(path,record);self.cancelled[job_id]=threading.Event();self.pool.submit(self._run,job_id,rows,ablations)
            return record
        except Exception:
            self.slots.release()
            if path.exists() and path.resolve().parent==self.root.resolve():shutil.rmtree(path)
            raise

    def _run(self,job_id,rows,ablations):
        path=self._path(job_id);output=path/'results';output.mkdir()
        measurements=[];failures=[];missing={};completed=0;successful=0
        try:
            with self.service.gate:
                self._update(job_id,status='running')
                for index,row in enumerate(rows):
                    if self.cancelled[job_id].is_set():break
                    try:
                        decoded=self.service.decode(Path(row['input']).read_bytes());rgb=decoded.rgb
                        reference=self.service.decode(Path(row['reference']).read_bytes()) if row['reference'] else None
                        if reference and (reference.original_size!=decoded.original_size or reference.rgb.shape!=rgb.shape):raise ImageInputError('Reference dimensions do not match input.')
                        if ablations:candidates,unavailable=run_ablations(rgb,self.service.deep);missing.update(unavailable)
                        else:
                            stats=analyze(rgb,maps=False)[0];classical=enhance_classical(rgb,stats);candidates={'classical':classical}
                            if self.service.deep.status()['available']:
                                deep=self.service.deep.enhance(rgb);candidates.update(deep=deep,hybrid=fuse_adaptive(rgb,classical,deep,stats)[0])
                            else:missing.update(deep=self.service.deep.status()['reason'],hybrid=self.service.deep.status()['reason'])
                        folder=output/f'{index:05d}';folder.mkdir();Image.fromarray(to_uint8(rgb)).save(folder/'original.png')
                        for mode,candidate in candidates.items():
                            Image.fromarray(to_uint8(candidate.image)).save(folder/f'{mode}.png')
                            metrics=evaluate(rgb,candidate.image,reference.rgb if reference else None,latency_ms=candidate.latency_ms,enable_iqa=self.service.settings.enable_iqa)
                            measurements.append({'key':row['key'],'mode':mode,'metrics':metrics,'parameters':candidate.parameters,
                                                 'diagnostics':diagnostics(rgb,candidate.image),'processed_size':list(decoded.processed_size),'resized':decoded.resized,
                                                 'artifact':f'/api/jobs/{job_id}/artifacts/{index:05d}/{mode}.png',
                                                 'original':f'/api/jobs/{job_id}/artifacts/{index:05d}/original.png'})
                        successful+=1
                    except Exception as exc:
                        logger.exception('Batch image failed: %s',row['key']);failures.append({'key':row['key'],'error':str(exc) if isinstance(exc,(ImageInputError,ValueError)) else f'Processing failed ({type(exc).__name__}).'})
                    completed+=1;self._update(job_id,completed=completed,successful=successful,failures=failures)
                report=write_report(output,measurements,model=self.service.deep.status(),settings=self.service.settings.model_dump(mode='json'),ablations=ablations,unavailable=missing,failures=failures)
                artifacts={file.relative_to(output).as_posix() for file in output.rglob('*') if file.is_file()}
                with zipfile.ZipFile(path/'results.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
                    for name in sorted(artifacts):archive.write(output/name,name)
                status='cancelled' if self.cancelled[job_id].is_set() else 'completed' if successful else 'failed'
                self._update(job_id,status=status,completed=completed,successful=successful,failures=failures,
                             report=report,artifacts=sorted(artifacts),download_url=f'/api/jobs/{job_id}/download',
                             error=None if successful else 'No image completed successfully; inspect the per-image failures.')
        except Exception as exc:
            logger.exception('Evaluation job failed');self._update(job_id,status='failed',error=f'Evaluation failed ({type(exc).__name__}).',failures=failures)
        finally:
            with self.lock:self.cancelled.pop(job_id,None)
            self.slots.release()

    def read(self,job_id):
        try:
            with self.lock:return json.loads((self._path(job_id)/'job.json').read_text(encoding='utf-8'))
        except (OSError,ValueError) as exc:raise KeyError('Job not found or expired.') from exc

    def cancel(self,job_id):
        with self.lock:
            record=self.read(job_id)
            if record['status'] not in {'queued','running','cancelling'}:return record
            if job_id not in self.cancelled:raise ValueError('Job was interrupted by a backend restart.')
            self.cancelled[job_id].set();self._update(job_id,status='cancelling');return self.read(job_id)

    def artifact(self,job_id,name):
        record=self.read(job_id);root=(self._path(job_id)/'results').resolve();path=(root/name).resolve()
        if name not in record.get('artifacts',[]) or not path.is_relative_to(root) or path.is_symlink():raise KeyError('Unknown job artifact')
        return path

    def cleanup(self):
        now=datetime.now(timezone.utc).timestamp()
        paths=sorted((p for p in self.root.iterdir() if p.is_dir() and not p.is_symlink() and VALID_ID.fullmatch(p.name)),key=lambda p:p.stat().st_mtime)
        for index,path in enumerate(paths):
            try:record=self.read(path.name)
            except KeyError:continue
            if record['status'] in {'queued','running','cancelling'}:continue
            if now-path.stat().st_mtime>self.service.settings.result_ttl_hours*3600 or index<len(paths)-9:
                if path.resolve().parent==self.root.resolve():shutil.rmtree(path)

    def close(self):
        with self.lock:flags=list(self.cancelled.values())
        for flag in flags:flag.set()
        self.pool.shutdown(wait=True,cancel_futures=True)
