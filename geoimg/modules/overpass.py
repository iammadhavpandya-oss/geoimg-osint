"""Generate Overpass QL from textual clues (e.g. 'fuel station within 50 m of a
railway and a Hindu temple'), with an overpass-turbo link. Optional polite
execution against the public Overpass API (single request, UA, timeout)."""
from __future__ import annotations

import re
from urllib.parse import quote

from .. import USER_AGENT

KEYWORDS = [  # (regex on lowercased text, OSM filter, label)
    (r"petrol|fuel|pump|indian oil|bharat petroleum|hindustan petroleum|\bhpcl\b|\bbpcl\b|\bcng\b", '["amenity"="fuel"]', "fuel station"),
    (r"railway|station|\bjn\b|junction|platform|रेल्वे|स्टेशन|स्थानक", '["railway"="station"]', "railway station"),
    (r"temple|mandir|मंदिर|देवस्थान", '["amenity"="place_of_worship"]["religion"="hindu"]', "Hindu temple"),
    (r"masjid|mosque|मशीद|मस्जिद", '["amenity"="place_of_worship"]["religion"="muslim"]', "mosque"),
    (r"church|chapel|चर्च", '["amenity"="place_of_worship"]["religion"="christian"]', "church"),
    (r"school|vidyalaya|शाळा|विद्यालय", '["amenity"="school"]', "school"),
    (r"hospital|clinic|रुग्णालय|अस्पताल", '["amenity"~"hospital|clinic"]', "hospital/clinic"),
    (r"\bbank\b|\bsbi\b|hdfc|icici|बँक|बैंक", '["amenity"="bank"]', "bank"),
    (r"\batm\b", '["amenity"="atm"]', "ATM"),
    (r"pharmacy|chemist|medical", '["amenity"="pharmacy"]', "pharmacy"),
    (r"police|पोलीस|पुलिस", '["amenity"="police"]', "police station"),
]


def clues_from_text(text: str) -> list[tuple[str, str]]:
    low = text.lower()
    return [(f, label) for rx, f, label in KEYWORDS if re.search(rx, low)]


def build(filters: list[tuple[str, str]], area: str | None = None, around: tuple[float, float, int] | None = None,
          within_m: int = 50) -> dict:
    if not filters:
        return {"status": "skipped", "reason": "no OSM-mappable clues"}
    lines = ["[out:json][timeout:90];"]
    if around:
        lat, lon, r = around
        scope = f"(around:{r},{lat},{lon})"
    else:
        a = f'area["name"="{area}"]["boundary"="administrative"]' if area else 'area["ISO3166-1"="IN"][admin_level=2]'
        lines.append(f"{a}->.searchArea;")
        scope = "(area.searchArea)"
    lines.append(f"nwr{filters[0][0]}{scope}->.c0;")
    for i, (f, _) in enumerate(filters[1:], 1):
        lines.append(f"nwr{f}(around.c0:{within_m * 4})->.c{i};")
    for i in range(1, len(filters)):
        lines.append(f"nwr.c0(around.c{i}:{within_m})->.c0;")
    lines.append(".c0 out center 50;")
    q = "\n".join(lines)
    desc = filters[0][1] + "".join(f" within {within_m} m of a {l}" for _, l in filters[1:])
    return {"status": "ok", "description": desc, "query": q,
            "overpass_turbo": "https://overpass-turbo.eu/?Q=" + quote(q) + "&R",
            "note": "Country-wide queries are heavy; narrow with --area or a candidate radius."}


def execute(query: str, endpoint: str = "https://overpass-api.de/api/interpreter") -> dict:
    try:
        import requests
        r = requests.post(endpoint, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=120)
        r.raise_for_status()
        els = r.json().get("elements", [])
    except Exception as e:
        return {"status": "error", "reason": str(e)[:300]}
    out = []
    for e in els[:50]:
        c = e.get("center") or {"lat": e.get("lat"), "lon": e.get("lon")}
        out.append({"type": e["type"], "id": e["id"], "name": e.get("tags", {}).get("name"), **c})
    return {"status": "ok", "count": len(els), "results": out}
