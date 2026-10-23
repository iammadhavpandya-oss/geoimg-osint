"""Privacy: remove GPS or all metadata from images (CyberWithMadhav awareness)."""
from __future__ import annotations

import shutil
import subprocess

from PIL import Image, ImageOps

try:
    import piexif
except ImportError:  # pragma: no cover
    piexif = None


def strip(src: str, dst: str, gps_only: bool = False) -> dict:
    if gps_only:
        if piexif is None:
            raise RuntimeError("piexif required for --gps-only")
        shutil.copyfile(src, dst)
        try:
            ex = piexif.load(dst)
            ex["GPS"] = {}
            ex["thumbnail"] = None  # thumbnails can leak pre-crop content
            piexif.insert(piexif.dump(ex), dst)
        except Exception:
            pass
        return {"output": dst, "mode": "gps-only"}
    if shutil.which("exiftool"):
        shutil.copyfile(src, dst)
        # bake orientation first so the picture doesn't rotate after stripping
        with Image.open(dst) as im:
            fixed = ImageOps.exif_transpose(im)
            fmt = im.format
            fixed.save(dst, fmt, **({"quality": 95} if fmt == "JPEG" else {}))
        subprocess.run(["exiftool", "-q", "-overwrite_original", "-all=", dst], check=True)
        return {"output": dst, "mode": "all (exiftool)"}
    with Image.open(src) as im:
        fixed = ImageOps.exif_transpose(im)
        clean = Image.new(fixed.mode, fixed.size)
        clean.putdata(list(fixed.getdata()))
        clean.save(dst, im.format, **({"quality": 95} if im.format == "JPEG" else {}))
    return {"output": dst, "mode": "all (pillow re-encode)"}
