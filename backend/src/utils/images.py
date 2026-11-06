import io
import warnings
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError


class ImageInputError(ValueError):
    pass


@dataclass
class DecodedImage:
    rgb: np.ndarray
    original_size: tuple[int, int]
    processed_size: tuple[int, int]
    format: str
    resized: bool


def decode_image(data: bytes, *, max_pixels: int, max_side: int) -> DecodedImage:
    """Decode by magic bytes; the sole internal format is RGB float32 in [0, 1]."""
    if not data:
        raise ImageInputError("The image file is empty.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                fmt = source.format or ""
                if fmt not in {"JPEG", "PNG", "WEBP"}:
                    raise ImageInputError("Supported image formats are JPEG, PNG, and WebP.")
                if source.width * source.height > max_pixels:
                    raise ImageInputError(f"Image exceeds the {max_pixels:,} pixel safety limit.")
                source.seek(0)
                image = ImageOps.exif_transpose(source)
                original = image.size
                if image.mode in {"I", "I;16", "I;16L", "I;16B"}:
                    # Preserve the exposure of 16-bit grayscale PNGs; RGB conversion
                    # alone would clamp every value above 255 to white.
                    samples = np.asarray(image, dtype=np.float32)
                    image = Image.fromarray(np.rint(np.clip(samples, 0, 65535) / 257).astype(np.uint8), "L")
                # Composite transparency onto black, appropriate for low-light scenes.
                if "A" in image.getbands() or "transparency" in image.info:
                    rgba = image.convert("RGBA")
                    image = Image.alpha_composite(Image.new("RGBA", rgba.size, (0, 0, 0, 255)), rgba)
                image = image.convert("RGB")
                image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
                rgb = np.asarray(image, dtype=np.float32) / 255.0
                return DecodedImage(np.ascontiguousarray(rgb), original, image.size, fmt, image.size != original)
    except ImageInputError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ImageInputError("The file is not a valid, safely decodable image.") from exc


def to_uint8(rgb: np.ndarray) -> np.ndarray:
    return np.rint(np.clip(np.nan_to_num(rgb), 0, 1) * 255).astype(np.uint8)


def luminance(rgb: np.ndarray) -> np.ndarray:
    # Display-referred Rec.709 luma, consistently used throughout this project.
    return np.asarray(rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32), np.float32)


def guided_filter(guide: np.ndarray, source: np.ndarray, radius: int = 12, eps: float = .003) -> np.ndarray:
    size = (2 * radius + 1, 2 * radius + 1)
    mean = lambda x: cv2.boxFilter(x, -1, size, borderType=cv2.BORDER_REFLECT)
    mu_i, mu_p = mean(guide), mean(source)
    covariance = mean(guide * source) - mu_i * mu_p
    variance = np.maximum(mean(guide * guide) - mu_i * mu_i, 0)
    a = covariance / (variance + eps)
    b = mu_p - a * mu_i
    return mean(a) * guide + mean(b)


def normalize_map(array: np.ndarray) -> np.ndarray:
    high = float(np.percentile(array, 98))
    return np.clip(array / max(high, 1e-6), 0, 1).astype(np.float32)
