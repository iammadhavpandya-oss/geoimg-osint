"""HTML report rendering (Leaflet map with uncertainty circle) + PDF/PNG export via headless Chromium."""
from __future__ import annotations

import base64
import json
import shutil
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))


def _img_b64(path, max_side: int = 640) -> str | None:
    """Embed a downscaled JPEG copy so reports stay small."""
    try:
        import io
        from PIL import Image
        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((max_side, max_side))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def render_html(res: dict, thumb_b64: str, out_dir: Path) -> str:
    ela = _img_b64(res["manipulation"]["ela"].get("ela_image", ""))
    gc = res.get("geoclip", {})
    gch = _img_b64(gc["heatmap"]) if gc.get("heatmap") else None
    return env.get_template("report.html").render(r=res, thumb=thumb_b64, ela=ela, geoclip_heatmap=gch,
                                                   loc_json=json.dumps(res.get("location")))


def chrome() -> str | None:
    for c in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        if shutil.which(c):
            return shutil.which(c)
    return None


def to_pdf(html_path: Path, pdf_path: Path) -> str | None:
    c = chrome()
    if c:
        subprocess.run([c, "--headless=new", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=8000",
                        "--no-pdf-header-footer", f"--print-to-pdf={pdf_path}", Path(html_path).resolve().as_uri()],
                       capture_output=True, timeout=120)
        if Path(pdf_path).exists():
            return str(pdf_path)
    try:
        from weasyprint import HTML  # no JS -> map tile area will be blank
        HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        return str(pdf_path)
    except Exception:
        return None


def to_png(html_path: Path, png_path: Path, width=1280, height=2400) -> str | None:
    c = chrome()
    if not c:
        return None
    subprocess.run([c, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                    "--virtual-time-budget=10000", f"--window-size={width},{height}",
                    f"--screenshot={png_path}", Path(html_path).resolve().as_uri()], capture_output=True, timeout=120)
    return str(png_path) if Path(png_path).exists() else None
