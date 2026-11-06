"""Optional photographic finish, kept separate from research/model outputs."""
import cv2
import numpy as np

from backend.src.utils.images import luminance


def vivid_finish(rgb: np.ndarray) -> np.ndarray:
    image = np.clip(rgb, 0, 1).astype(np.float32)
    y = luminance(image)
    # Lift midtones while anchoring black and white. No extra lift in highlights.
    lifted = y + .55 * y * (1 - y) ** 2
    smooth = cv2.GaussianBlur(lifted, (0, 0), 1.1)
    detail = lifted - smooth
    # A small threshold limits sharpening of weak residual noise.
    detail = np.sign(detail) * np.maximum(np.abs(detail) - .003, 0)
    target = np.clip(lifted + np.clip(detail * .22, -.012, .012) * (1 - y), 0, 1)
    base = image * (target / np.maximum(y, 1e-6))[:, :, None]
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    # Vibrance favours muted colours; skin-like hues receive a gentler increase.
    skin = ((hsv[:, :, 0] < 50) & (hsv[:, :, 1] > .12) & (hsv[:, :, 1] < .7))
    boost = 1 + .32 * (1 - hsv[:, :, 1]) * np.where(skin, .45, 1)
    chroma = (base - target[:, :, None]) * boost[:, :, None]
    # Compress chroma to fit RGB gamut without clipping individual channels.
    positive = np.maximum(chroma.max(axis=2), 1e-6)
    negative = np.maximum(-chroma.min(axis=2), 1e-6)
    scale = np.minimum(1, np.minimum((1 - target) / positive, target / negative))
    return np.clip(target[:, :, None] + chroma * scale[:, :, None], 0, 1).astype(np.float32)


def export_4k(rgb: np.ndarray) -> np.ndarray:
    """3840px long edge with original aspect ratio; interpolation, not super-resolution."""
    height, width = rgb.shape[:2]
    scale = 3840 / max(height, width)
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return np.clip(cv2.resize(rgb, size, interpolation=cv2.INTER_LANCZOS4 if scale > 1 else cv2.INTER_AREA), 0, 1)
