"""Verification links around a candidate location: street-level imagery
(Mapillary/KartaView/Street View), satellite (Esri World Imagery, Esri Wayback
historical, Sentinel Hub EO Browser, Google Earth). Mapillary API used only if
MAPILLARY_TOKEN is set."""
from __future__ import annotations

import os

from .. import USER_AGENT


def links(lat: float, lon: float) -> dict:
    return {
        "Google Street View": f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lon}",
        "Mapillary": f"https://www.mapillary.com/app/?lat={lat}&lng={lon}&z=17",
        "KartaView": f"https://kartaview.org/map/@{lat},{lon},17z",
        "Esri World Imagery": f"https://www.arcgis.com/home/webmap/viewer.html?center={lon},{lat}&level=17&basemapUrl=https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer",
        "Esri Wayback (historical)": f"https://livingatlas.arcgis.com/wayback/#mapCenter={lon}%2C{lat}%2C17",
        "Sentinel Hub EO Browser": f"https://apps.sentinel-hub.com/eo-browser/?zoom=15&lat={lat}&lng={lon}",
        "Google Earth Web": f"https://earth.google.com/web/@{lat},{lon},100a,800d,35y,0h,0t,0r",
    }


def mapillary_nearby(lat: float, lon: float, d: float = 0.002, limit: int = 5) -> dict:
    tok = os.environ.get("MAPILLARY_TOKEN")
    if not tok:
        return {"status": "skipped", "reason": "MAPILLARY_TOKEN not set (links still provided)"}
    try:
        import requests
        r = requests.get("https://graph.mapillary.com/images",
                         params={"access_token": tok, "fields": "id,captured_at,thumb_256_url,computed_geometry",
                                 "bbox": f"{lon-d},{lat-d},{lon+d},{lat+d}", "limit": limit},
                         headers={"User-Agent": USER_AGENT}, timeout=20)
        r.raise_for_status()
        return {"status": "ok", "images": r.json().get("data", [])}
    except Exception as e:
        return {"status": "error", "reason": str(e)}
