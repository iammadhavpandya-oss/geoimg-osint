"""Dominant colour extraction (simple k-means via Pillow quantize)."""
from PIL import Image


def dominant(path: str, k: int = 6) -> list[dict]:
    with Image.open(path) as im:
        small = im.convert("RGB").resize((160, 160))
    q = small.quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[: k * 3]
    counts = sorted(q.getcolors(), reverse=True)
    total = sum(c for c, _ in counts)
    out = []
    for c, idx in counts:
        r, g, b = pal[idx * 3: idx * 3 + 3]
        out.append({"hex": f"#{r:02x}{g:02x}{b:02x}", "share": round(c / total, 3)})
    return out
