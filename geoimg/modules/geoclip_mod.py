"""Optional GeoCLIP (Vivanco et al., NeurIPS 2023) top-k GPS prediction + heatmap.
Heavy (PyTorch). Lazy: only used if `geoclip` is importable, or in the Python
given by GEOIMG_GEOCLIP_PYTHON (a separate venv), so the core tool stays light.
PIGEON (Haas et al., CVPR 2024) is documented only (no public pip package)."""
from __future__ import annotations

import json
import os
import subprocess
import sys

RUNNER = r"""
import json, sys
from geoclip import GeoCLIP
m = GeoCLIP()
gps, prob = m.predict(sys.argv[1], top_k=int(sys.argv[2]))
print(json.dumps([{"lat": float(g[0]), "lon": float(g[1]), "p": float(p)} for g, p in zip(gps.tolist(), prob.tolist())]))
"""


def _python() -> str | None:
    env = os.environ.get("GEOIMG_GEOCLIP_PYTHON")
    if env and os.path.exists(env):
        return env
    try:
        import geoclip  # noqa: F401
        return sys.executable
    except ImportError:
        return None


def heatmap_png(preds: list[dict], out_path: str) -> str | None:
    """Simple equirectangular scatter heatmap (no basemap, Pillow only)."""
    from PIL import Image, ImageDraw
    W, H = 1024, 512
    im = Image.new("RGB", (W, H), (15, 23, 42))
    d = ImageDraw.Draw(im)
    for x in range(0, W, W // 12):
        d.line([(x, 0), (x, H)], fill=(40, 50, 70))
    for y in range(0, H, H // 6):
        d.line([(0, y), (W, y)], fill=(40, 50, 70))
    pmax = max(p["p"] for p in preds) or 1
    for p in preds:
        x = (p["lon"] + 180) / 360 * W
        y = (90 - p["lat"]) / 180 * H
        r = 4 + 16 * p["p"] / pmax
        d.ellipse([x - r, y - r, x + r, y + r], fill=(239, 68, 68))
    im.save(out_path)
    return out_path


def run(path: str, top_k: int = 5, heatmap_out: str | None = None) -> dict:
    py = _python()
    if not py:
        return {"status": "skipped", "reason": "geoclip not installed. Install in a separate venv: "
                "python3 -m venv ~/geoclip-venv && ~/geoclip-venv/bin/pip install torch --index-url "
                "https://download.pytorch.org/whl/cpu && ~/geoclip-venv/bin/pip install geoclip; then "
                "export GEOIMG_GEOCLIP_PYTHON=~/geoclip-venv/bin/python"}
    try:
        r = subprocess.run([py, "-c", RUNNER, path, str(top_k)], capture_output=True, text=True, timeout=900)
        preds = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:
        return {"status": "error", "reason": f"GeoCLIP failed: {e}; stderr tail: {r.stderr[-300:] if 'r' in dir() else ''}"}
    res = {"status": "ok", "top_k": preds, "note": "GeoCLIP is a learned prior; often country/region-level accurate at best."}
    if heatmap_out:
        res["heatmap"] = heatmap_png(preds, heatmap_out)
    return res
