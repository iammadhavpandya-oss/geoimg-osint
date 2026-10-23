"""Generate synthetic test images (no real people/places photographed):
1. gateway_gps.jpg      - synthetic scene + GPS EXIF at Gateway of India (18.9220, 72.8347)
2. signboard_nogps.jpg  - shop signboard with English + Marathi + Gujarati text, plate, PIN, STD phone; no GPS
3. tampered_gps.jpg     - GPS image whose EXIF thumbnail is a different picture + a copy-moved block
"""
from __future__ import annotations

import io
import os
import random
import sys

import piexif
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from geoimg.modules.metadata import decimal_to_dms_rational  # noqa: E402

NOTO = "/usr/share/fonts/truetype/noto/"


def font(name, size):
    for p in (NOTO + name, "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def scene(seed=1, w=1200, h=800):
    random.seed(seed)
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h // 2):  # sky gradient
        d.line([(0, y), (w, y)], fill=(90 + y // 8, 150 + y // 10, 230))
    d.rectangle([0, h // 2, w, h], fill=(60, 110, 150))  # sea
    # stylised arch monument
    d.rectangle([420, 180, 780, 420], fill=(214, 180, 130))
    d.rectangle([540, 260, 660, 420], fill=(90, 120, 160))
    d.pieslice([540, 200, 660, 320], 180, 360, fill=(90, 120, 160))
    for x in (440, 740):
        d.rectangle([x, 140, x + 30, 190], fill=(200, 165, 115))
    for _ in range(400):  # texture/noise so ELA & ORB have something
        x, y = random.randrange(w), random.randrange(h // 2, h)
        d.point((x, y), fill=(random.randrange(40, 90), random.randrange(90, 140), 170))
    # deterministic fine texture (buildings/foliage stand-in) so ELA & ORB have real detail
    import numpy as np
    rng = np.random.default_rng(seed)
    arr = np.asarray(im).astype(np.int16)
    blocks = rng.integers(-35, 35, size=(-(-h // 6), -(-w // 6), 3))
    arr += np.kron(blocks, np.ones((6, 6, 1), dtype=np.int16))[:h, :w]
    return Image.fromarray(np.clip(arr, 0, 255).astype("uint8"))


def thumb_bytes(img):
    t = img.copy()
    t.thumbnail((160, 120))
    b = io.BytesIO()
    t.save(b, "JPEG", quality=80)
    return b.getvalue()


def gps_exif(lat, lon, alt, thumb, when="2026:01:26 16:30:00"):
    zeroth = {piexif.ImageIFD.Make: b"geoimg-test", piexif.ImageIFD.Model: b"SyntheticCam X1",
              piexif.ImageIFD.Software: b"geoimg make_samples.py", piexif.ImageIFD.Orientation: 1,
              piexif.ImageIFD.DateTime: when.encode()}
    exif = {piexif.ExifIFD.DateTimeOriginal: when.encode(), piexif.ExifIFD.LensModel: b"Synthetic 26mm"}
    gps = {piexif.GPSIFD.GPSLatitudeRef: b"N" if lat >= 0 else b"S",
           piexif.GPSIFD.GPSLatitude: decimal_to_dms_rational(lat),
           piexif.GPSIFD.GPSLongitudeRef: b"E" if lon >= 0 else b"W",
           piexif.GPSIFD.GPSLongitude: decimal_to_dms_rational(lon),
           piexif.GPSIFD.GPSAltitudeRef: 0, piexif.GPSIFD.GPSAltitude: (int(alt * 100), 100),
           piexif.GPSIFD.GPSDateStamp: when[:10].encode()}
    return piexif.dump({"0th": zeroth, "Exif": exif, "GPS": gps, "1st": {}, "thumbnail": thumb})


def signboard(w=1400, h=900):
    im = Image.new("RGB", (w, h), (235, 235, 228))
    d = ImageDraw.Draw(im)
    d.rectangle([40, 40, w - 40, 470], fill=(250, 214, 40), outline=(30, 30, 30), width=8)
    d.text((80, 60), "SHREE GANESH GENERAL STORES", font=font("NotoSans-Bold.ttf", 64), fill=(160, 20, 20))
    d.text((80, 150), "श्री गणेश जनरल स्टोअर्स", font=font("NotoSansDevanagari-Bold.ttf", 72), fill=(20, 20, 120))
    d.text((80, 260), "आमच्या येथे सर्व वस्तू मिळतील आणि घरपोच सेवा आहे", font=font("NotoSansDevanagari-Bold.ttf", 46), fill=(20, 20, 20))
    d.text((80, 340), "Station Road, Vasai (W) - 401202", font=font("NotoSans-Bold.ttf", 48), fill=(20, 20, 20))
    d.text((80, 405), "Tel: 0250 2321234   Mob: +91 98200 12345", font=font("NotoSans-Bold.ttf", 44), fill=(20, 20, 20))
    d.rectangle([40, 520, 700, 620], fill=(255, 255, 255), outline=(0, 0, 0), width=5)
    d.text((70, 525), "MH 48 AB 1234", font=font("NotoSans-Bold.ttf", 70), fill=(0, 0, 0))
    d.rectangle([760, 520, w - 40, 860], fill=(20, 90, 40))
    d.text((790, 540), "NH 48", font=font("NotoSans-Bold.ttf", 60), fill=(255, 255, 255))
    d.text((790, 630), "VIRAR 12 km", font=font("NotoSans-Bold.ttf", 54), fill=(255, 255, 255))
    d.text((790, 720), "Petrol Pump  500 m", font=font("NotoSans-Bold.ttf", 46), fill=(255, 255, 255))
    d.text((70, 680), "શ્રી ગણેશ સ્ટોર્સ", font=font("NotoSansGujarati-Bold.ttf", 64), fill=(120, 20, 20))
    d.text((70, 780), "Near Vasai Road Railway Station", font=font("NotoSans-Bold.ttf", 40), fill=(40, 40, 40))
    return im


def main(out="samples"):
    os.makedirs(out, exist_ok=True)
    a = scene(1)
    a.save(f"{out}/gateway_gps.jpg", "JPEG", quality=92, exif=gps_exif(18.9220, 72.8347, 10.0, thumb_bytes(a)))
    signboard().save(f"{out}/signboard_nogps.jpg", "JPEG", quality=92)
    # tampered: copy-move a block and keep the ORIGINAL (different) picture as EXIF thumbnail
    t = scene(2)
    other = Image.new("RGB", (1200, 800), (200, 30, 30))
    ImageDraw.Draw(other).ellipse([300, 100, 900, 700], fill=(20, 20, 20))
    block = t.crop((450, 200, 650, 400))
    t.paste(block, (850, 450))
    t.save(f"{out}/tampered_gps.jpg", "JPEG", quality=92, exif=gps_exif(19.3919, 72.8397, 8.0, thumb_bytes(other)))
    print("samples written to", out)


if __name__ == "__main__":
    main(*(sys.argv[1:2] or []))
