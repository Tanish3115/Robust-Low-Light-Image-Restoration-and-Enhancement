import hashlib
import importlib.util
import os
import threading
from time import perf_counter

import numpy as np

from backend.app.config import Settings
from backend.src.classical.pipeline import PipelineResult


class ModelUnavailable(RuntimeError):
    pass


class RetinexformerEngine:
    """One cached official model. Never falls back to fake neural output."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = None
        self.device = "cpu"
        self.reason = "Retinexformer has not been initialized."
        self.lock = threading.RLock()
        self.signature = None
        self.checkpoint_sha256 = None
        self.warning = None

    def prepare(self):
        path = self.settings.absolute(self.settings.checkpoint)
        try:signature = (str(path), path.stat().st_mtime_ns if path.is_file() else None)
        except OSError:
            self.model=None;self.reason='The configured checkpoint cannot be read.';self.checkpoint_sha256=None
            return
        with self.lock:
            if signature == self.signature:
                return
            self.signature = signature
            self.model = None
            self.checkpoint_sha256=None
            self.warning=None
            if not path.is_file():
                self.reason = f"Pretrained checkpoint missing: {path.name}. Run scripts/setup_model.py and restart the backend."
                return
            if importlib.util.find_spec("torch") is None or importlib.util.find_spec("einops") is None:
                self.reason = "Install backend/requirements-deep.txt to enable genuine Retinexformer inference."
                return
            try:
                import torch
                from backend.src.deep.vendor.retinexformer_arch import RetinexFormer
                requested = self.settings.device.lower()
                if requested not in {"auto", "cpu", "cuda"}:
                    raise ValueError("LUMA_DEVICE must be auto, cpu, or cuda.")
                # Explicit cuda configuration also falls back to CPU when unavailable.
                self.device = "cuda" if requested != "cpu" and torch.cuda.is_available() else "cpu"
                if self.device == "cpu":
                    torch.set_num_threads(min(4, max(1, os.cpu_count() or 1)))
                model = RetinexFormer(in_channels=3, out_channels=3, n_feat=40, stage=1, num_blocks=[1, 2, 2])
                checkpoint = torch.load(path, map_location="cpu", weights_only=True)
                state = checkpoint
                if isinstance(checkpoint, dict):
                    for key in ("params_ema", "params", "state_dict"):
                        if key in checkpoint:
                            state = checkpoint[key]
                            break
                if not isinstance(state, dict) or not state:
                    raise ValueError("Checkpoint does not contain a state dictionary.")
                state = {key.removeprefix("module."): value for key, value in state.items()}
                model.load_state_dict(state, strict=True)
                model.eval()
                try:model.to(self.device)
                except (RuntimeError,AssertionError) as exc:
                    if self.device!='cuda':raise
                    self.device='cpu';model.to('cpu');torch.set_num_threads(min(4,max(1,os.cpu_count() or 1)))
                    self.warning=f'CUDA initialization failed ({type(exc).__name__}); using real CPU inference.'
                with path.open("rb") as stream:
                    self.checkpoint_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
                self.model = model
                self.reason = None
            except Exception as exc:
                self.reason = f"Retinexformer setup failed ({type(exc).__name__}): {str(exc)[:350]}"

    def status(self) -> dict:
        self.prepare()
        return {"available": self.model is not None, "label": "Official Retinexformer · LOL-v1",
                "reason": self.reason, "device": self.device,
                "warning": self.warning,
                "checkpoint_sha256": self.checkpoint_sha256,
                "configuration": {"n_feat": 40, "stage": 1, "num_blocks": [1, 2, 2]}}

    def _infer_patch(self, patch: np.ndarray) -> np.ndarray:
        import torch
        import torch.nn.functional as functional
        h, w = patch.shape[:2]
        tensor = torch.from_numpy(np.ascontiguousarray(patch.transpose(2, 0, 1))).unsqueeze(0).to(self.device)
        pad_h, pad_w = (-h) % 8, (-w) % 8
        if pad_h or pad_w:
            tensor = functional.pad(tensor, (0, pad_w, 0, pad_h), mode="reflect" if h > pad_h and w > pad_w else "replicate")
        result = self.model(tensor)[:, :, :h, :w]
        if not torch.isfinite(result).all():
            raise ModelUnavailable("Retinexformer produced non-finite pixels; output rejected.")
        return result.clamp(0, 1).squeeze(0).permute(1, 2, 0).cpu().numpy().astype(np.float32)

    @staticmethod
    def tile_starts(length: int, size: int, overlap: int) -> list[int]:
        if length <= size:
            return [0]
        starts = list(range(0, length - size + 1, size - overlap))
        if starts[-1] != length - size:
            starts.append(length - size)
        return starts

    def enhance(self, rgb: np.ndarray) -> PipelineResult:
        started=perf_counter()
        try:return self._enhance(rgb)
        except Exception as exc:
            if self.device!='cuda':raise
            import torch
            if not isinstance(exc,torch.cuda.OutOfMemoryError):raise
            with self.lock:
                self.model.to('cpu');self.device='cpu'
                torch.set_num_threads(min(4,max(1,os.cpu_count() or 1)))
                self.warning='CUDA memory was exhausted; the image was retried using genuine CPU inference.'
                try:torch.cuda.empty_cache()
                except (RuntimeError,AssertionError):pass
                result=self._enhance(rgb)
                result.latency_ms=(perf_counter()-started)*1000
                result.parameters['fallback_warning']=self.warning
                return result

    def _enhance(self, rgb: np.ndarray) -> PipelineResult:
        self.prepare()
        if self.model is None:
            raise ModelUnavailable(self.reason)
        import torch
        start = perf_counter()
        size = self.settings.tile_size
        overlap = min(self.settings.tile_overlap, size // 2)
        h, w = rgb.shape[:2]
        with self.lock, torch.inference_mode():
            if max(h, w) <= size:
                output = self._infer_patch(rgb)
                count = 1
            else:
                output = np.zeros_like(rgb)
                weights = np.zeros((h, w), np.float32)
                count = 0
                for y in self.tile_starts(h, size, overlap):
                    for x in self.tile_starts(w, size, overlap):
                        patch = rgb[y:y+size, x:x+size]
                        prediction = self._infer_patch(patch)
                        ph, pw = patch.shape[:2]
                        # Positive raised-cosine window: no zero-weight image boundary.
                        wy = np.maximum(np.hanning(ph), .05).astype(np.float32)
                        wx = np.maximum(np.hanning(pw), .05).astype(np.float32)
                        window = wy[:, None] * wx[None, :]
                        output[y:y+ph, x:x+pw] += prediction * window[:, :, None]
                        weights[y:y+ph, x:x+pw] += window
                        count += 1
                output /= np.maximum(weights[:, :, None], 1e-8)
            if self.device == "cuda":
                torch.cuda.synchronize()
        latency = (perf_counter() - start) * 1000
        return PipelineResult(np.clip(output, 0, 1), {"deep": np.clip(output, 0, 1)},
                              {"model": "Retinexformer", "checkpoint_sha256": self.checkpoint_sha256,
                               "device": self.device, "tile_size": size, "overlap": overlap, "tiles": count,
                               "device_warning": self.warning,
                               "padding_multiple": 8, "n_feat": 40, "stage": 1, "num_blocks": [1, 2, 2]}, latency)
