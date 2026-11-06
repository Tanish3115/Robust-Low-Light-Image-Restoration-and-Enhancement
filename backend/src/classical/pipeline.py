from dataclasses import dataclass
from time import perf_counter

import cv2
import numpy as np

from backend.src.analysis.analyzer import analyze
from backend.src.utils.images import guided_filter, luminance, to_uint8


@dataclass
class PipelineResult:
    image: np.ndarray
    artifacts: dict[str, np.ndarray]
    parameters: dict
    latency_ms: float


def select_parameters(stats: dict, strength: float = 1.) -> dict:
    severity = stats["underexposure_severity"]
    noise = stats["noise_estimate"]
    return {
        "gamma": float(np.clip(1 - .64 * severity * strength, .28, 1)),
        "max_gain": float(1 + 4.5 * severity * strength),
        "illumination_floor": float(.025 + min(noise * 2, .06)),
        "denoise_mix": float(np.clip(noise * 10 + severity * .1, 0, .65)),
        "bilateral_sigma": float(np.clip(.025 + noise * 2, .025, .14)),
        "clahe_clip": float(np.clip(1.8 - noise * 18, 1., 1.8)),
        "clahe_mix": float(np.clip(.12 + .14 * severity - noise * 3, .04, .26) * min(strength, 1.5)),
        "white_balance_mix": float(min(.5, stats["colour_imbalance"]) * .6),
        "saturation_gain": float(np.clip(1 + (.3 - stats["saturation"]) * .08 * severity, .98, 1.025)),
        "strength": strength,
    }


def enhance_classical(rgb: np.ndarray, stats: dict | None = None, *, strength: float = 1.,
                      denoise: bool = True, clahe: bool = True, colour: bool = True, quality: bool = True) -> PipelineResult:
    start = perf_counter()
    stats = stats or analyze(rgb, maps=False)[0]
    p = select_parameters(stats, strength)
    y = luminance(rgb)
    maximum = rgb.max(axis=2)
    radius = max(2, min(24, min(y.shape) // 24))
    light = np.clip(guided_filter(y, maximum, radius), p["illumination_floor"], 1)
    reflectance = np.clip(rgb / light[:, :, None], 0, 1)
    gain = np.clip(np.power(light, p["gamma"] - 1), 1, p["max_gain"])
    # Protect already bright light sources locally, without lifting black to gray.
    protect = np.clip((y - .65) / .3, 0, 1)
    gain = 1 + (gain - 1) * (1 - protect)
    retinex = np.clip(rgb * gain[:, :, None], 0, 1)
    denoised = retinex
    if denoise and p["denoise_mix"] > .015:
        smooth = cv2.bilateralFilter(retinex, 5, p["bilateral_sigma"], 3)
        denoised = retinex * (1 - p["denoise_mix"]) + smooth * p["denoise_mix"]
    contrasted = denoised
    grid = (max(1, min(8, rgb.shape[1] // 32)), max(1, min(8, rgb.shape[0] // 32)))
    if clahe:
        lab = cv2.cvtColor(to_uint8(denoised), cv2.COLOR_RGB2LAB)
        equalized = cv2.createCLAHE(clipLimit=p["clahe_clip"], tileGridSize=grid).apply(lab[:, :, 0])
        lab[:, :, 0] = np.rint(lab[:, :, 0] * (1 - p["clahe_mix"]) + equalized * p["clahe_mix"]).astype(np.uint8)
        contrasted = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB).astype(np.float32) / 255
        # CLAHE must not invent illumination in completely clipped shadows.
        support = np.clip(y / .015, 0, 1)[:, :, None]
        contrasted = contrasted * support + denoised * (1 - support)
    corrected = contrasted
    wb_gains = np.ones(3, np.float32)
    if colour:
        valid = (y > .02) & (y < .9)
        means = contrasted[valid].mean(axis=0) if valid.any() else contrasted.mean(axis=(0, 1))
        wb_gains = np.clip(np.mean(means) / np.maximum(means, .01), .8, 1.25)
        wb_gains = 1 + (wb_gains - 1) * p["white_balance_mix"]
        corrected = np.clip(contrasted * wb_gains, 0, 1)
        hsv = cv2.cvtColor(corrected.astype(np.float32), cv2.COLOR_RGB2HSV)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * p["saturation_gain"], 0, 1)
        corrected = np.clip(cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB), 0, 1)
    # Soft preservation near original highlights.
    final = np.clip(corrected * (1 - protect[:, :, None]) + rgb * protect[:, :, None], 0, 1).astype(np.float32)
    from backend.src.evaluation.artifacts import suppress_artifacts
    final, corrections, risk_maps = suppress_artifacts(rgb, final) if quality else (final, [], {})
    p['quality_corrections'] = corrections
    p['quality_safeguards'] = quality
    p.update({"clahe_grid": list(grid), "white_balance_gains": wb_gains.tolist(),
              "denoise_enabled": denoise, "clahe_enabled": clahe, "colour_enabled": colour})
    return PipelineResult(final, {"illumination_original": maximum, "illumination_refined": light,
                                  "reflectance": reflectance, "retinex": retinex, "denoised": denoised,
                                  "clahe": contrasted, "colour_corrected": corrected, "classical": final, **risk_maps},
                          p, (perf_counter() - start) * 1000)
