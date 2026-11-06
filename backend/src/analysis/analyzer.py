import cv2
import numpy as np
from scipy.ndimage import uniform_filter

from backend.src.utils.images import guided_filter, luminance, normalize_map, to_uint8


def noise_sigma(y: np.ndarray) -> float:
    """MAD of a diagonal Haar high-pass in the flattest half of the image.

    Display-referred estimate, not a calibrated sensor-noise measurement.
    The kernel has unit L2 norm, so sigma has normalized intensity units.
    """
    if min(y.shape) < 4:
        return 0.0
    residual = cv2.filter2D(y, -1, np.array([[1, -1], [-1, 1]], np.float32) / 2)
    gx = cv2.Sobel(y, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(y, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.hypot(gx, gy)
    mask = grad <= np.percentile(grad, 50)
    values = residual[mask]
    return float(np.median(np.abs(values - np.median(values))) / .67448975)


def analyze(rgb: np.ndarray, *, maps: bool = True) -> tuple[dict, dict[str, np.ndarray]]:
    h, w = rgb.shape[:2]
    small = cv2.resize(rgb, (max(1, round(w * min(1, 768 / max(h, w)))),
                             max(1, round(h * min(1, 768 / max(h, w))))), interpolation=cv2.INTER_AREA)
    y = luminance(small)
    mean, median = float(y.mean()), float(np.median(y))
    illumination = cv2.GaussianBlur(y, (0, 0), max(1., min(y.shape) / 24))
    local_mean = uniform_filter(y, size=15, mode="reflect")
    local_std = np.sqrt(np.maximum(uniform_filter(y * y, size=15, mode="reflect") - local_mean**2, 0))
    gx, gy = cv2.Sobel(y, cv2.CV_32F, 1, 0), cv2.Sobel(y, cv2.CV_32F, 0, 1)
    edges = cv2.Canny(to_uint8(y), 40, 100)
    channels = small.mean(axis=(0, 1))
    hsv = cv2.cvtColor(small, cv2.COLOR_RGB2HSV)
    hist, _ = np.histogram(y, bins=64, range=(0, 1))
    severity = "extremely dark" if mean < .065 else "severely underexposed" if mean < .16 else "moderately underexposed" if mean < .29 else "mildly underexposed" if mean < .43 else "well exposed / bright"
    stats = {
        "mean_brightness": mean, "median_luminance": median,
        "dark_pixel_percentage": float(np.mean(y < .15) * 100),
        "underexposure_severity": float(np.clip((.43 - mean) / .43, 0, 1)),
        "classification": severity, "illumination_variance": float(illumination.var()),
        "nonuniform_illumination": float(illumination.std() / max(mean, .02)),
        "noise_estimate": noise_sigma(y), "edge_density": float((edges > 0).mean()),
        "texture_strength": float(np.hypot(gx, gy).mean() / 4),
        "local_contrast": float(local_std.mean()),
        "dynamic_range": float(np.percentile(y, 99) - np.percentile(y, 1)),
        "channel_means": [float(c) for c in channels],
        "colour_imbalance": float(channels.std() / max(channels.mean(), .01)),
        "saturation": float(hsv[:, :, 1].mean()),
        "highlight_clipping": float(np.mean(np.any(small >= 254 / 255, axis=2))),
        "shadow_clipping": float(np.mean(y <= 1 / 255)),
        "histogram": [{"bin": round((i + .5) * 255 / 64, 2), "count": int(n)} for i, n in enumerate(hist)],
        "analysis_size": [small.shape[1], small.shape[0]],
        "noise_protocol": "Flat-region diagonal Haar MAD; display intensity [0,1]; heuristic, texture-dependent.",
    }
    visuals = {}
    if maps:
        full_y = luminance(rgb)
        maximum = rgb.max(axis=2)
        refined = np.clip(guided_filter(full_y, maximum, max(2, min(24, min(h, w) // 24))), 0, 1)
        residual = np.abs(full_y - cv2.GaussianBlur(full_y, (0, 0), 1.))
        visuals = {"illumination_original": maximum, "illumination_refined": refined,
                   "noise_map": normalize_map(residual), "edge_map": edges.astype(np.float32) / 255,
                   "contrast_map": normalize_map(local_std)}
    return stats, visuals
