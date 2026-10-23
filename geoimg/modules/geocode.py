"""Reverse geocoding via OpenStreetMap Nominatim, respecting the usage policy:
custom User-Agent, max 1 request/second, local on-disk cache."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .. import USER_AGENT

CACHE = Path(os.environ.get("GEOIMG_CACHE", Path.home() / ".cache" / "geoimg")) / "nominatim.json"
_last_call = [0.0]


def links(lat: float, lon: float, zoom: int = 17) -> dict:
    return {
        "google_maps": f"https://www.google.com/maps?q={lat},{lon}",
        "osm": f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map={zoom}/{lat}/{lon}",
        "osm_embed": (f"https://www.openstreetmap.org/export/embed.html?bbox={lon-0.005},{lat-0.003},"
                      f"{lon+0.005},{lat+0.003}&layer=mapnik&marker={lat},{lon}"),
    }


def _load_cache() -> dict:
    try:
        return json.loads(CACHE.read_text())
    except Exception:
        return {}


def reverse(lat: float, lon: float, offline: bool = False) -> dict:
    key = f"{lat:.5f},{lon:.5f}"
    cache = _load_cache()
    if key in cache:
        return {**cache[key], "cached": True}
    if offline or os.environ.get("GEOIMG_OFFLINE"):
        return {"status": "skipped", "reason": "offline mode"}
    try:
        import requests
    except ImportError:
        return {"status": "skipped", "reason": "requests not installed"}
    wait = 1.0 - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    try:
        r = requests.get("https://nominatim.openstreetmap.org/reverse",
                         params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 18,
                                 "addressdetails": 1, "accept-language": "en"},
                         headers={"User-Agent": USER_AGENT}, timeout=15)
        _last_call[0] = time.time()
        r.raise_for_status()
        j = r.json()
    except Exception as e:  # network down, rate limit, etc.
        return {"status": "error", "reason": f"Nominatim unavailable: {e.__class__.__name__}: {e}"}
    res = {"status": "ok", "display_name": j.get("display_name"), "address": j.get("address", {}),
           "osm_type": j.get("osm_type"), "osm_id": j.get("osm_id"),
           "attribution": "Data © OpenStreetMap contributors, ODbL"}
    cache[key] = res
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=1))
    return res


def search(query: str, offline: bool = False) -> dict:
    """Forward geocode a place name (used to place a pin for text-derived region clues)."""
    key = "q:" + query.lower()
    cache = _load_cache()
    if key in cache:
        return {**cache[key], "cached": True}
    if offline or os.environ.get("GEOIMG_OFFLINE"):
        return {"status": "skipped", "reason": "offline mode"}
    import requests
    wait = 1.0 - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search",
                         params={"q": query, "format": "jsonv2", "limit": 1, "accept-language": "en"},
                         headers={"User-Agent": USER_AGENT}, timeout=15)
        _last_call[0] = time.time()
        r.raise_for_status()
        j = r.json()
    except Exception as e:
        return {"status": "error", "reason": f"Nominatim unavailable: {e}"}
    if not j:
        return {"status": "error", "reason": "no match"}
    res = {"status": "ok", "lat": float(j[0]["lat"]), "lon": float(j[0]["lon"]), "display_name": j[0]["display_name"]}
    cache[key] = res
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=1))
    return res
