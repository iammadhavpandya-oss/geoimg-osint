"""EXIF/XMP metadata extraction (exiftool preferred, Pillow/piexif fallback)
plus embedded-thumbnail vs main-image perceptual-hash comparison."""
from __future__ import annotations

import io
import json
import shutil
import subprocess
from fractions import Fraction

from PIL import Image, ExifTags

try:
    import piexif
except ImportError:  # pragma: no cover
    piexif = None
try:
    import imagehash
except ImportError:  # pragma: no cover
    imagehash = None

INTERESTING = [
    "Make", "Model", "LensModel", "Software", "DateTimeOriginal", "CreateDate",
    "ModifyDate", "OffsetTimeOriginal", "Orientation", "ImageWidth", "ImageHeight",
    "GPSLatitude", "GPSLongitude", "GPSAltitude", "GPSImgDirection", "GPSDateStamp",
    "GPSTimeStamp", "Artist", "Copyright", "XMP:CreatorTool", "SerialNumber",
]


def _to_float(v) -> float:
    if isinstance(v, tuple) and len(v) == 2:
        return v[0] / v[1] if v[1] else 0.0
    if isinstance(v, Fraction):
        return float(v)
    return float(v)


def dms_to_decimal(dms, ref: str | None) -> float:
    """Convert (deg, min, sec) (rationals or floats) + hemisphere ref to decimal degrees."""
    d, m, s = (_to_float(x) for x in dms)
    dec = d + m / 60.0 + s / 3600.0
    if ref and str(ref).upper().strip(" \x00")[:1] in ("S", "W"):
        dec = -dec
    return round(dec, 7)


def decimal_to_dms_rational(value: float):
    """Inverse of dms_to_decimal; returns piexif rational triple."""
    value = abs(value)
    d = int(value)
    m_f = (value - d) * 60
    m = int(m_f)
    s = round((m_f - m) * 60 * 10000)
    return ((d, 1), (m, 1), (s, 10000))


def _exiftool(path: str) -> dict | None:
    if not shutil.which("exiftool"):
        return None
    try:
        out = subprocess.run(["exiftool", "-j", "-n", "-G0", "-a", "-u", path],
                             capture_output=True, text=True, timeout=30)
        data = json.loads(out.stdout)[0]
    except Exception:
        return None
    flat = {}
    for k, v in data.items():
        if k.startswith("File:") or k.startswith("ExifTool:") or k == "SourceFile":
            continue
        short = k.split(":", 1)[-1]
        flat.setdefault(short, v)
        if k.startswith("XMP:"):
            flat[k] = v
    # Composite tags carry the signed (hemisphere-applied) decimal values
    for t in ("GPSLatitude", "GPSLongitude", "GPSAltitude"):
        if f"Composite:{t}" in data:
            flat[t] = data[f"Composite:{t}"]
    return flat


def _pillow(path: str) -> dict:
    flat: dict = {}
    with Image.open(path) as im:
        flat["ImageWidth"], flat["ImageHeight"] = im.size
        exif = im.getexif()
        for tag, val in exif.items():
            flat[ExifTags.TAGS.get(tag, str(tag))] = val
        try:
            ifd = exif.get_ifd(ExifTags.IFD.Exif)
            for tag, val in ifd.items():
                flat[ExifTags.TAGS.get(tag, str(tag))] = val
        except Exception:
            pass
        gps = {}
        try:
            gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
            for tag, val in gps_ifd.items():
                gps[ExifTags.GPSTAGS.get(tag, str(tag))] = val
        except Exception:
            pass
        if "GPSLatitude" in gps and "GPSLongitude" in gps:
            flat["GPSLatitude"] = dms_to_decimal(gps["GPSLatitude"], gps.get("GPSLatitudeRef"))
            flat["GPSLongitude"] = dms_to_decimal(gps["GPSLongitude"], gps.get("GPSLongitudeRef"))
        if "GPSAltitude" in gps:
            alt = _to_float(gps["GPSAltitude"])
            if gps.get("GPSAltitudeRef") in (1, b"\x01"):
                alt = -alt
            flat["GPSAltitude"] = round(alt, 2)
        for k in ("GPSDateStamp", "GPSImgDirection"):
            if k in gps:
                flat[k] = str(gps[k]) if k == "GPSDateStamp" else _to_float(gps[k])
        xmp = im.info.get("xmp") or im.info.get("XML:com.adobe.xmp")
        if xmp:
            flat["XMP:raw_present"] = True
    for k, v in list(flat.items()):
        if isinstance(v, bytes):
            flat[k] = v[:64].decode("utf-8", "replace").strip("\x00")
        elif not isinstance(v, (int, float, str, bool)):
            flat[k] = str(v)
    return flat


def extract_thumbnail(path: str) -> Image.Image | None:
    if piexif is None:
        return None
    try:
        ex = piexif.load(path)
        thumb = ex.get("thumbnail")
        if thumb:
            return Image.open(io.BytesIO(thumb)).convert("RGB")
    except Exception:
        return None
    return None


def thumbnail_check(path: str) -> dict:
    thumb = extract_thumbnail(path)
    if thumb is None:
        return {"status": "skipped", "reason": "no embedded EXIF thumbnail"}
    if imagehash is None:
        return {"status": "skipped", "reason": "imagehash not installed"}
    with Image.open(path) as im:
        main = im.convert("RGB")
        main_h = imagehash.phash(main)
    thumb_h = imagehash.phash(thumb)
    dist = main_h - thumb_h
    mismatch = dist > 12
    return {
        "status": "ok", "thumb_size": thumb.size, "main_phash": str(main_h),
        "thumb_phash": str(thumb_h), "hamming_distance": int(dist), "mismatch": bool(mismatch),
        "note": ("thumbnail mismatch, possible edit (the embedded preview differs from the image)"
                 if mismatch else "embedded thumbnail matches main image"),
    }


def extract(path: str) -> dict:
    engine = "exiftool"
    raw = _exiftool(path)
    if raw is None:
        engine = "pillow"
        raw = _pillow(path)
    summary = {k: raw[k] for k in INTERESTING if k in raw}
    gps = None
    lat, lon = raw.get("GPSLatitude"), raw.get("GPSLongitude")
    try:
        if lat is not None and lon is not None:
            lat, lon = float(lat), float(lon)
            if not (lat == 0 and lon == 0):
                gps = {"lat": round(lat, 7), "lon": round(lon, 7)}
                if raw.get("GPSAltitude") is not None:
                    gps["alt"] = float(raw["GPSAltitude"])
    except (TypeError, ValueError):
        gps = None
    return {"engine": engine, "summary": summary, "gps": gps,
            "timestamp": raw.get("DateTimeOriginal") or raw.get("CreateDate"),
            "raw_count": len(raw), "raw": {k: raw[k] for k in list(raw)[:200]},
            "thumbnail": thumbnail_check(path)}
