from functools import lru_cache
import threading

import cv2
import numpy as np
from skimage.metrics import peak_signal_noise_ratio, structural_similarity

from backend.src.analysis.analyzer import analyze, noise_sigma
from backend.src.utils.images import luminance

_iqa_lock = threading.Lock()


def metric(value: float | None, direction: str, reason: str | None = None, **extra) -> dict:
    return {"value": value, "direction": direction, "available": value is not None,
            "reason": reason, **extra}


@lru_cache(maxsize=2)
def _iqa_model(name: str):
    import torch
    from backend.app.config import get_settings
    settings=get_settings()
    torch.hub.set_dir(str(settings.absolute(settings.metric_cache_dir)))
    import pyiqa
    return pyiqa.create_metric(name, device="cpu")


def evaluate(original: np.ndarray, enhanced: np.ndarray, reference: np.ndarray | None = None,
             *, latency_ms: float = 0, enable_iqa: bool = False) -> dict:
    before, after = luminance(original), luminance(enhanced)
    sigma_in, sigma_out = noise_sigma(before), noise_sigma(after)
    gx = lambda x: np.hypot(cv2.Sobel(x, cv2.CV_32F, 1, 0), cv2.Sobel(x, cv2.CV_32F, 0, 1)).flatten()
    g_in, g_out = gx(before), gx(after)
    centered_in, centered_out = g_in - g_in.mean(), g_out - g_out.mean()
    denominator = float(np.linalg.norm(centered_in) * np.linalg.norm(centered_out))
    edge = float(np.dot(centered_in, centered_out) / denominator) if denominator > 1e-9 else None
    unavailable = "Requires an aligned reference image with identical dimensions."
    result = {
        "psnr": metric(None, "higher", unavailable),
        "ssim": metric(None, "higher", unavailable),
        "lpips": metric(None, "lower", "Requires a reference and optional pyiqa model weights."),
        "niqe": metric(None, "lower", "Optional pyiqa is disabled; no substitute score is used."),
        "latency_ms": metric(float(latency_ms), "lower"),
        "noise_suppression": metric(float(1 - sigma_out / sigma_in) if sigma_in > 1e-6 else None,
                                    "higher", "Flat-region Haar MAD change; exposure/texture confounded, not ground-truth noise removal."),
        "edge_preservation": metric(edge, "higher", "Pearson correlation of input/output Sobel magnitudes; not reference fidelity."),
        "highlight_clipping": metric(float(np.any(enhanced >= 254 / 255, axis=2).mean()), "lower"),
        "noise_estimate": metric(sigma_out, "lower", "Display intensity [0,1]; flat-region Haar MAD."),
    }
    if reference is not None:
        if reference.shape != enhanced.shape:
            raise ValueError("Reference dimensions must match the processed image. No automatic alignment is performed.")
        mse = float(np.mean((reference.astype(np.float64) - enhanced) ** 2))
        if mse == 0:
            result["psnr"] = metric(None, "higher", "Identical images: PSNR is positive infinity.", available=True, infinite=True)
        else:
            result["psnr"] = metric(float(peak_signal_noise_ratio(reference, enhanced, data_range=1.)), "higher")
        size = min(reference.shape[:2])
        if size >= 3:
            window = min(7, size if size % 2 else size - 1)
            result["ssim"] = metric(float(structural_similarity(reference, enhanced, data_range=1.,
                                                                channel_axis=2, win_size=window)), "higher")
        else:
            result["ssim"] = metric(None, "higher", "SSIM needs dimensions of at least 3 pixels.")
    if enable_iqa:
        try:
            import torch
            tensor = lambda x: torch.from_numpy(np.ascontiguousarray(x.transpose(2, 0, 1))).unsqueeze(0)
        except ImportError:
            for name in ("niqe", "lpips"):
                result[name]["reason"] = "Optional IQA requires PyTorch and requirements-iqa.txt."
        else:
            # NIQE estimates a patch-feature covariance; a single 96px block
            # is insufficient. Require at least a 2x2 grid of 96px blocks.
            for name, minimum in (("niqe", 192), ("lpips", 64)):
                if name == "lpips" and reference is None:
                    continue
                if min(enhanced.shape[:2]) < minimum:
                    result[name] = metric(None, "lower", f"{name.upper()} requires images at least {minimum}×{minimum}.")
                    continue
                try:
                    with _iqa_lock, torch.inference_mode():
                        args = [tensor(enhanced)] if name == "niqe" else [tensor(enhanced), tensor(reference)]
                        value = float(_iqa_model(name)(*args).item())
                    result[name] = metric(value if np.isfinite(value) else None, "lower",
                                          None if np.isfinite(value) else "Metric returned a non-finite score.")
                except Exception as exc:
                    # Each optional metric fails independently; restoration remains usable.
                    result[name] = metric(None, "lower", f"Optional {name.upper()} unavailable: {type(exc).__name__}. Install requirements-iqa.txt and provision metric weights.")
    return result


def diagnostics(original: np.ndarray, output: np.ndarray) -> list[dict]:
    before, _ = analyze(original, maps=False)
    after, _ = analyze(output, maps=False)
    warnings = []
    def add(code, problem, stage, action, limitation):
        warnings.append({"code": code, "problem": problem, "stage": stage, "action": action, "limitation": limitation})
    if before["mean_brightness"] < .065:
        add("extreme_darkness", "Extremely low input luminance.", "Acquisition", "The input was flagged for extreme darkness; classical gain is bounded when that pipeline is used.", "Missing or clipped scene information cannot be recovered reliably.")
    if before["shadow_clipping"] > .1:
        add("clipped_shadows", "More than 10% of input pixels are clipped shadows.", "Acquisition", "Clipped shadows were flagged; classical CLAHE uses a black-region support mask.", "True texture in clipped shadows is unavailable.")
    if before["noise_estimate"] > .025:
        add("input_noise", "High flat-region noise estimate.", "Acquisition / denoising", "Noise was measured before and after processing; classical denoising adapts to the input estimate.", "Texture and compression may affect the noise estimate.")
    if before["nonuniform_illumination"] > .6:
        add("uneven_light", "Strongly nonuniform illumination.", "Illumination", "Uneven lighting was flagged; classical/hybrid processing uses spatial correction when selected.", "Large illumination transitions can remain visible.")
    if after["highlight_clipping"] > before["highlight_clipping"] + .02:
        add("highlight_clipping", "Output clipping increased by more than two percentage points.", "Restoration", "Highlight preservation is applied where supported.", "Inspect bright sources before using the result.")
    if after["colour_imbalance"] > before["colour_imbalance"] + .15:
        add("colour_shift", "Mean-channel imbalance increased.", "Colour reconstruction", "The output was flagged for colour review; hybrid confidence penalizes this when the controller is used.", "A neutral target is needed to distinguish a cast from scene colour.")
    if after["noise_estimate"] > max(before["noise_estimate"] * 2.2, .035):
        add("noise_amplification", "Output high-pass noise estimate is elevated.", "Illumination / contrast", "The output was flagged for noise review; classical gains and contrast are bounded when used.", "This detector also responds to newly visible texture.")
    if before["texture_strength"] > .01 and after["texture_strength"] < before["texture_strength"] * .6:
        add("detail_loss", "Gradient texture strength fell substantially.", "Denoising / reconstruction", "Hybrid confidence includes edge and texture agreement.", "Check fine details at full size.")
    from backend.src.evaluation.artifacts import assess_artifacts
    regional, _ = assess_artifacts(original, output)
    return warnings + regional
