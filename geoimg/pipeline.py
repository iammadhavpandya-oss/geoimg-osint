"""Orchestrates all modules for one image and writes JSON/HTML (+PDF) reports."""
from __future__ import annotations

import base64
import datetime as _dt
import io
import json
import os
from pathlib import Path

from PIL import Image, ImageOps

from . import __version__
from .modules import colors, evidence, geocode, india, manipulation, metadata, ocr, overpass
from .modules import reverse_search, sun, verify_links, vision_llm, geoclip_mod


def _thumb_b64(path: str, size=480) -> str:
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((size, size))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def _parse_exif_dt(s):
    try:
        return _dt.datetime.strptime(str(s)[:19], "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None


def analyze(path: str, out_dir: str = "reports", offline: bool = False, use_llm: bool = True,
            use_geoclip: bool = False, overpass_run: bool = False, shadow_azimuth: float | None = None,
            shadow_ratio: float | None = None, utc_offset: float = 5.5, public_url: str | None = None,
            pdf: bool = False, html: bool = True, extra: dict | None = None) -> dict:
    p = Path(path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = p.stem
    res: dict = {"tool": f"geoimg {__version__}", "file": str(p.resolve()), "name": p.name,
                 "analyzed_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds")}
    if extra:
        res.update(extra)
    md = metadata.extract(str(p))
    res["metadata"] = md
    gps = md.get("gps") or (extra or {}).get("video_gps")
    if gps and not md.get("gps"):
        md["gps"] = gps
    if gps:
        res["geocode"] = geocode.reverse(gps["lat"], gps["lon"], offline=offline)
    res["ocr"] = ocr.run(str(p))
    text = res["ocr"].get("text", "")
    res["india"] = india.analyze(text)
    res["colors"] = colors.dominant(str(p))
    res["manipulation"] = manipulation.run(str(p), md, str(out / f"{stem}_ela.png"))
    res["vision_llm"] = vision_llm.run(str(p), context=text) if use_llm else {"status": "skipped", "reason": "disabled"}
    res["geoclip"] = (geoclip_mod.run(str(p), heatmap_out=str(out / f"{stem}_geoclip.png")) if use_geoclip
                      else {"status": "skipped", "reason": "not requested (--geoclip)"})

    ev = evidence.build(res)
    loc = evidence.locate(ev, geocode.search, offline=offline)
    res["evidence"] = ev
    res["location"] = loc
    if loc:
        res["links"] = geocode.links(loc["lat"], loc["lon"])
        res["verify_links"] = verify_links.links(loc["lat"], loc["lon"])
        res["mapillary"] = verify_links.mapillary_nearby(loc["lat"], loc["lon"])

    filt = overpass.clues_from_text(text)
    around = (loc["lat"], loc["lon"], int(min(loc["radius_km"], 30) * 1000)) if loc else None
    ov = overpass.build(filt, around=around)
    if ov.get("status") == "ok" and overpass_run and not offline:
        ov["execution"] = overpass.execute(ov["query"])
    res["overpass"] = ov

    dt = _parse_exif_dt(md.get("timestamp"))
    if dt and (shadow_azimuth is not None or shadow_ratio is not None or loc):
        dt_utc = (dt - _dt.timedelta(hours=utc_offset)).replace(tzinfo=_dt.timezone.utc)
        res["sun"] = sun.analyze(dt_utc, shadow_azimuth, shadow_ratio,
                                 loc["lat"] if loc else None, loc["lon"] if loc else None)
        res["sun"]["assumed_utc_offset_h"] = utc_offset
    else:
        res["sun"] = {"status": "skipped", "reason": "needs EXIF time plus a candidate location or --shadow-azimuth"}

    thumb = _thumb_b64(str(p))
    res["reverse_search"] = reverse_search.links(public_url)
    (out / f"{stem}_reverse.html").write_text(reverse_search.aggregation_page(p.name, thumb, public_url))
    res["outputs"] = {"json": str(out / f"{stem}.json"), "reverse_search_page": str(out / f"{stem}_reverse.html"),
                      "ela": str(out / f"{stem}_ela.png")}
    if html:
        from .report import render_html
        res["outputs"]["html"] = str(out / f"{stem}.html")
        (out / f"{stem}.html").write_text(render_html(res, thumb, out))
        if pdf:
            from .report import to_pdf
            res["outputs"]["pdf"] = to_pdf(out / f"{stem}.html", out / f"{stem}.pdf")
    Path(res["outputs"]["json"]).write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str))
    return res
