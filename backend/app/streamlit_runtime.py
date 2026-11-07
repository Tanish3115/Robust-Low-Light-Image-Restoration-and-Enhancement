"""Bounded, in-memory demo runtime. Does not change the FastAPI service."""
import hashlib
import io
from pathlib import Path
import tempfile
import threading
from time import perf_counter
import urllib.request

from PIL import Image

from backend.app.config import ROOT, Settings
from backend.src.analysis.analyzer import analyze
from backend.src.classical.finish import vivid_finish
from backend.src.classical.pipeline import enhance_classical
from backend.src.deep.inference import ModelUnavailable, RetinexformerEngine
from backend.src.evaluation.metrics import diagnostics, evaluate
from backend.src.utils.images import decode_image, ImageInputError, to_uint8

CHECKPOINT_SHA256 = "9b4810dc51322fab70be8658ee0ad1df64a54aa814497b7849767baa2ff32cd1"
CHECKPOINT_URL = "https://drive.usercontent.google.com/download?id=1xDwQtTCj3tlAVCTJgYrzonBGVwqeOhKu&export=download&confirm=t"


def download_checkpoint(destination: Path):
    """Download only the verified LOL-v1 checkpoint; publish atomically."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        request = urllib.request.Request(CHECKPOINT_URL, headers={"User-Agent": "LumaRestore/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            if 'text/html' in response.headers.get('Content-Type', ''):
                raise ModelUnavailable('Model host returned a web page. Retry later or install official weights manually.')
            with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.download', delete=False) as target:
                temporary = Path(target.name)
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > 20 * 1024**2:
                        raise ModelUnavailable('Checkpoint download exceeded its safety limit.')
                    target.write(chunk)
        with temporary.open('rb') as source:
            if hashlib.file_digest(source, 'sha256').hexdigest() != CHECKPOINT_SHA256:
                raise ModelUnavailable('Checkpoint checksum mismatch; download rejected.')
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def png_bytes(rgb):
    buffer = io.BytesIO()
    Image.fromarray(to_uint8(rgb)).save(buffer, format='PNG')
    return buffer.getvalue()


class DemoRuntime:
    def __init__(self, checkpoint: Path = ROOT / 'checkpoints/LOL_v1.pth'):
        self.engine = RetinexformerEngine(Settings(_env_file=None, checkpoint=checkpoint, device='cpu',
                                                   tile_size=128, tile_overlap=16, enable_iqa=False))
        self.gate = threading.BoundedSemaphore(1)

    def run(self, data: bytes, *, mode='auto', strength=1., vivid=True, max_side=512,
            reference_data: bytes | None = None, allow_download=True):
        if mode not in {'auto', 'classical', 'deep', 'hybrid'}:
            raise ImageInputError('Unknown enhancement mode.')
        if max_side not in {256, 384, 512, 768} or not .3 <= strength <= 1.5:
            raise ImageInputError('Unsupported processing limits.')
        if not self.gate.acquire(blocking=False):
            raise RuntimeError('Another image is processing. Please retry after it finishes.')
        try:
            start = perf_counter()
            def decode(payload):
                if len(payload) > 10 * 1024**2:
                    raise ImageInputError('Maximum upload size is 10 MB.')
                return decode_image(payload, max_pixels=20_000_000, max_side=max_side)
            decoded = decode(data)
            rgb = decoded.rgb
            reference = decode(reference_data) if reference_data is not None else None
            if reference and reference.original_size != decoded.original_size:
                raise ImageInputError('Reference must have the same oriented dimensions and alignment.')
            stats, _ = analyze(rgb, maps=False)
            notices = []
            controller = None
            neural = None
            needs_neural = mode in {'deep', 'hybrid'} or (mode == 'auto' and stats['underexposure_severity'] > .25)
            if needs_neural:
                try:
                    path = self.engine.settings.absolute(self.engine.settings.checkpoint)
                    if not path.is_file() and allow_download:
                        download_checkpoint(path)
                    neural = self.engine.enhance(rgb)
                except Exception as exc:
                    if mode != 'auto':
                        raise ModelUnavailable(f'Neural inference unavailable: {exc}') from exc
                    notices.append(f'Auto used classical enhancement because neural inference was unavailable: {exc}')
            if mode == 'deep':
                chosen = neural
                executed = 'deep'
            else:
                chosen = enhance_classical(rgb, stats, strength=strength)
                executed = 'classical'
                if neural is not None:
                    from backend.src.hybrid.controller import fuse_adaptive
                    chosen, controller = fuse_adaptive(rgb, chosen, neural, stats)
                    executed = controller['selected_mode']
            output = vivid_finish(chosen.image) if vivid else chosen.image
            metrics = evaluate(rgb, output, reference.rgb if reference else None,
                               latency_ms=(perf_counter() - start) * 1000, enable_iqa=False)
            if decoded.resized:
                notices.append(f'Processing copy resized to {decoded.processed_size[0]} x {decoded.processed_size[1]} pixels.')
            return {'original_png': png_bytes(rgb), 'enhanced_png': png_bytes(output),
                    'report': {'requested_mode': mode, 'executed_mode': executed, 'vivid_finish': vivid,
                               'analysis': stats, 'parameters': chosen.parameters, 'controller': controller,
                               'metrics': metrics, 'diagnostics': diagnostics(rgb, output),
                               'original_size': list(decoded.original_size), 'processed_size': list(decoded.processed_size),
                               'notices': notices,
                               'deployment': 'CPU Streamlit demo; LPIPS/NIQE disabled to limit memory.'}}
        finally:
            self.gate.release()
