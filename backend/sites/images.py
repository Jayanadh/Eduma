"""Uploaded brand images are opened with Pillow, checked and re-encoded, so what is stored is a plain image of an
allowed type with no metadata (camera details, GPS) and nothing hidden after the image data.
shortcut: no anti-virus scan; re-encoding is the content check. Add a scanner adapter before accepting documents."""

import hashlib
import io

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

MAX_BYTES = 5 * 1024 * 1024
MAX_SIDE = 4000
FORMATS = {"PNG": ("image/png", "png"), "JPEG": ("image/jpeg", "jpg"), "WEBP": ("image/webp", "webp")}
UNREADABLE = "This file is not a PNG, JPEG or WebP image we can read."


def _refuse(message: str):
    raise ValidationError({"file": [message]})


def clean_image(upload) -> tuple[ContentFile, dict]:
    if upload.size == 0:
        _refuse("The file is empty.")
    if upload.size > MAX_BYTES:
        _refuse("Images can be up to 5 MB.")
    try:
        # Opening reads only the header, so the size check below runs before any pixels are decoded.
        with Image.open(upload) as image:
            if image.format not in FORMATS:
                _refuse(UNREADABLE)
            if image.width > MAX_SIDE or image.height > MAX_SIDE:
                _refuse(f"Images can be up to {MAX_SIDE} × {MAX_SIDE} pixels.")
            fmt = image.format
            image.load()
            # Turn phone photos the right way up before their orientation tag is dropped with the rest of the metadata.
            image = ImageOps.exif_transpose(image)
            if fmt == "JPEG" and image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            out = io.BytesIO()
            image.save(out, format=fmt, **({"quality": 88} if fmt != "PNG" else {"optimize": True}))
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
        _refuse(UNREADABLE)
    data = out.getvalue()
    content_type, ext = FORMATS[fmt]
    info = {
        "content_type": content_type,
        "width": image.width,
        "height": image.height,
        "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "ext": ext,
    }
    return ContentFile(data, name=f"image.{ext}"), info
