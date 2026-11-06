import io

import numpy as np
from PIL import Image
import pytest

from backend.src.utils.images import decode_image, ImageInputError


@pytest.mark.parametrize("format,mode", [("JPEG","RGB"),("PNG","L"),("PNG","RGBA"),("WEBP","RGB"),("PNG","P")])
def test_real_decoding(format, mode):
    image = Image.new(mode,(80,40))
    buffer=io.BytesIO(); image.save(buffer,format=format)
    decoded=decode_image(buffer.getvalue(),max_pixels=10000,max_side=64)
    assert decoded.rgb.shape == (32,64,3)
    assert decoded.rgb.dtype == np.float32
    assert np.isfinite(decoded.rgb).all()
    assert decoded.rgb.min() >= 0 and decoded.rgb.max() <= 1
    assert decoded.resized


def test_transparency_is_composited():
    buffer=io.BytesIO(); Image.new("RGBA",(8,8),(255,255,255,0)).save(buffer,format="PNG")
    decoded=decode_image(buffer.getvalue(),max_pixels=100,max_side=64)
    assert decoded.rgb.max()==0


def test_exif_orientation():
    image=Image.new("RGB",(20,40)); exif=Image.Exif();exif[274]=6
    buffer=io.BytesIO();image.save(buffer,format="JPEG",exif=exif)
    decoded=decode_image(buffer.getvalue(),max_pixels=1000,max_side=100)
    assert decoded.original_size == (40,20)


@pytest.mark.parametrize("data", [b"", b"fake image", b"\x89PNG\r\n\x1a\ninvalid"])
def test_invalid(data):
    with pytest.raises(ImageInputError):decode_image(data,max_pixels=100,max_side=100)


def test_pixel_safety_limit():
    buffer=io.BytesIO();Image.new("RGB",(101,101)).save(buffer,format="PNG")
    with pytest.raises(ImageInputError, match="pixel safety"):
        decode_image(buffer.getvalue(),max_pixels=10000,max_side=100)


def test_sixteen_bit_grayscale_keeps_its_exposure():
    buffer=io.BytesIO();Image.fromarray(np.full((8,8),6554,np.uint16)).save(buffer,format='PNG')
    decoded=decode_image(buffer.getvalue(),max_pixels=1000,max_side=100)
    assert .09 < decoded.rgb.mean() < .11
