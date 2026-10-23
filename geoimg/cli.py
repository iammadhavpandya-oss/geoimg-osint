"""geoimg command-line interface."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

from . import __version__

BANNER = "geoimg — educational image-geolocation OSINT. Use only on your own images, CTFs or authorised investigations."
IMG_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".heic"}


def _summary(r: dict):
    loc = r.get("location")
    print(f"\n== {r['name']} ==")
    if loc:
        print(f"  location : {loc['lat']:.5f}, {loc['lon']:.5f} ±{loc['radius_km']} km  [{loc['label']}, conf {loc['confidence']:.0%}]")
    else:
        print("  location : not determined")
    g = r.get("geocode") or {}
    if g.get("display_name"):
        print(f"  address  : {g['display_name']}")
    elif g.get("reason"):
        print(f"  geocode  : {g['reason']}")
    for e in r["evidence"]["chain"][:8]:
        print(f"  - [{e['confidence']:.0%}] {e['clue']} -> {e['inference']}")
    for k, v in r["outputs"].items():
        print(f"  {k:<20}: {v}")


def cmd_analyze(a):
    paths = []
    for p in a.inputs:
        P = Path(p)
        paths += sorted(x for x in P.iterdir() if x.suffix.lower() in IMG_EXT) if P.is_dir() else [P]
    from .pipeline import analyze
    results = []
    for p in paths:
        r = analyze(str(p), a.out, offline=a.offline, use_llm=not a.no_llm, use_geoclip=a.geoclip,
                    overpass_run=a.overpass_run, shadow_azimuth=a.shadow_azimuth, shadow_ratio=a.shadow_ratio,
                    utc_offset=a.utc_offset, public_url=a.public_url, pdf=a.pdf)
        results.append(r)
        if a.json:
            print(json.dumps(r, indent=2, ensure_ascii=False, default=str))
        else:
            _summary(r)
    return 0


def cmd_strip(a):
    from .modules.strip import strip
    for src in a.inputs:
        s = Path(src)
        dst = Path(a.output) if a.output and len(a.inputs) == 1 else s.with_name(f"{s.stem}_clean{s.suffix}")
        r = strip(str(s), str(dst), gps_only=a.gps_only)
        print(f"stripped ({r['mode']}): {s} -> {dst}")
    return 0


def cmd_video(a):
    from .modules import video
    from .pipeline import analyze
    info = video.probe(a.input)
    print(json.dumps({k: v for k, v in info.items() if k != "tags"}, indent=2, default=str))
    frames = video.keyframes(a.input, os.path.join(a.out, Path(a.input).stem + "_frames"), a.max_frames)
    print(f"{len(frames)} keyframes extracted")
    extra = {"video_source": a.input, "video_gps": info.get("gps")}
    for f in frames:
        _summary(analyze(f, a.out, offline=a.offline, use_llm=not a.no_llm, extra=extra))
    return 0


def cmd_sun(a):
    from .modules.sun import analyze
    t = dt.datetime.fromisoformat(a.datetime)
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone(dt.timedelta(hours=a.utc_offset)))
    print(json.dumps(analyze(t, a.shadow_azimuth, a.shadow_ratio, a.lat, a.lon), indent=2))
    return 0


def cmd_overpass(a):
    from .modules import overpass
    filt = overpass.clues_from_text(" ".join(a.clues))
    around = (a.lat, a.lon, a.radius) if a.lat is not None else None
    q = overpass.build(filt, area=a.area, around=around, within_m=a.within)
    if q.get("status") == "ok" and a.run:
        q["execution"] = overpass.execute(q["query"])
    print(json.dumps(q, indent=2, ensure_ascii=False))
    return 0


def cmd_web(a):
    from .web import create_app
    if a.host not in ("127.0.0.1", "localhost"):
        print("Refusing to bind to non-loopback host; the web UI is local-only.", file=sys.stderr)
        return 2
    create_app(a.out).run(host=a.host, port=a.port, debug=False)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="geoimg", description=BANNER)
    ap.add_argument("--version", action="version", version=f"geoimg {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("analyze", help="analyse image(s) or a folder and write JSON+HTML reports")
    s.add_argument("inputs", nargs="+")
    s.add_argument("-o", "--out", default="reports")
    s.add_argument("--offline", action="store_true", help="no network calls (Nominatim/Overpass)")
    s.add_argument("--no-llm", action="store_true", help="skip vision-LLM even if API key is set")
    s.add_argument("--geoclip", action="store_true", help="run optional GeoCLIP top-k (heavy)")
    s.add_argument("--overpass-run", action="store_true", help="execute generated Overpass query (1 polite request)")
    s.add_argument("--shadow-azimuth", type=float, help="measured shadow direction, degrees from true north")
    s.add_argument("--shadow-ratio", type=float, help="shadow length / object height")
    s.add_argument("--utc-offset", type=float, default=5.5, help="timezone of EXIF clock (default IST 5.5)")
    s.add_argument("--public-url", help="public URL of the image, enables one-click reverse search links")
    s.add_argument("--pdf", action="store_true", help="also export PDF (headless Chromium / WeasyPrint)")
    s.add_argument("--json", action="store_true", help="print full JSON to stdout")
    s.set_defaults(func=cmd_analyze)

    s = sub.add_parser("strip", help="remove GPS/EXIF metadata (privacy)")
    s.add_argument("inputs", nargs="+")
    s.add_argument("-o", "--output")
    s.add_argument("--gps-only", action="store_true", help="remove only GPS (+ thumbnail), keep camera info")
    s.set_defaults(func=cmd_strip)

    s = sub.add_parser("video", help="extract keyframes with ffmpeg and analyse each")
    s.add_argument("input")
    s.add_argument("-o", "--out", default="reports")
    s.add_argument("--max-frames", type=int, default=6)
    s.add_argument("--offline", action="store_true")
    s.add_argument("--no-llm", action="store_true")
    s.set_defaults(func=cmd_video)

    s = sub.add_parser("sun", help="sun/shadow consistency check or latitude scan")
    s.add_argument("--datetime", required=True, help="ISO time, e.g. 2026-03-21T12:30:00")
    s.add_argument("--utc-offset", type=float, default=5.5)
    s.add_argument("--shadow-azimuth", type=float)
    s.add_argument("--shadow-ratio", type=float)
    s.add_argument("--lat", type=float)
    s.add_argument("--lon", type=float)
    s.set_defaults(func=cmd_sun)

    s = sub.add_parser("overpass", help="build Overpass QL from clue words")
    s.add_argument("clues", nargs="+", help='e.g. "petrol pump" "railway station" "temple"')
    s.add_argument("--area", help="admin area name, e.g. Vasai-Virar")
    s.add_argument("--lat", type=float)
    s.add_argument("--lon", type=float)
    s.add_argument("--radius", type=int, default=5000)
    s.add_argument("--within", type=int, default=50)
    s.add_argument("--run", action="store_true")
    s.set_defaults(func=cmd_overpass)

    s = sub.add_parser("web", help="local web UI (127.0.0.1 only)")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=5055)
    s.add_argument("-o", "--out", default="reports")
    s.set_defaults(func=cmd_web)

    a = ap.parse_args(argv)
    print(BANNER, file=sys.stderr)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
