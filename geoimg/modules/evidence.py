"""Confidence-scored evidence chain (clue -> inference -> confidence) and a
best-candidate location with an uncertainty radius."""
from __future__ import annotations

import re

EDIT_SOFTWARE = re.compile(r"photoshop|gimp|lightroom|snapseed|picsart|canva|pixelmator|affinity", re.I)
RADIUS_KM = {"gps": 0.05, "rto": 25, "pin3": 30, "pin2": 250, "std": 30, "brand": 150, "script": 600,
             "llm": 100, "geoclip": 300, "marathi": 350}


def _clean(region: str) -> str:
    r = region.split("(")[0].split(";")[0]
    return r.split("/")[0].strip(" ,-")


def build(res: dict) -> dict:
    chain, cands = [], []
    md = res.get("metadata", {})
    manip = res.get("manipulation", {})
    penalties = []
    if md.get("thumbnail", {}).get("mismatch"):
        penalties.append("embedded thumbnail mismatch")
    sw = str(md.get("summary", {}).get("Software", ""))
    if EDIT_SOFTWARE.search(sw):
        penalties.append(f"edited with {sw}")
    if manip.get("ai", {}).get("ai_likelihood", 0) >= 0.5:
        penalties.append("AI-generation markers")
    if manip.get("clone", {}).get("flag"):
        penalties.append("possible copy-move")

    gps = md.get("gps")
    if gps:
        conf = 0.9 - 0.15 * len(penalties)
        chain.append({"clue": f"EXIF GPS {gps['lat']}, {gps['lon']}", "inference": "Device recorded this position at capture",
                      "confidence": round(max(conf, 0.3), 2), "source": "metadata",
                      "caveat": "GPS EXIF is trivially editable/spoofable" + (f"; integrity flags: {', '.join(penalties)}" if penalties else "")})
        cands.append({"label": "EXIF GPS", "lat": gps["lat"], "lon": gps["lon"], "radius_km": RADIUS_KM["gps"],
                      "confidence": round(max(conf, 0.3), 2)})
        geo = res.get("geocode", {})
        if geo.get("status") == "ok":
            chain.append({"clue": "Reverse geocode (Nominatim)", "inference": geo["display_name"], "confidence": round(max(conf - 0.05, 0.3), 2),
                          "source": "OpenStreetMap"})
    if md.get("timestamp"):
        chain.append({"clue": f"Timestamp {md['timestamp']}", "inference": "Capture time per camera clock (timezone often absent)",
                      "confidence": 0.6, "source": "metadata"})
    s = md.get("summary", {})
    if s.get("Make") or s.get("Model"):
        chain.append({"clue": f"Camera {s.get('Make', '')} {s.get('Model', '')}".strip(), "inference": "Device fingerprint (links photos from same device)",
                      "confidence": 0.7, "source": "metadata"})

    ocr = res.get("ocr", {})
    sc = ocr.get("scripts") or {}
    for h in sc.get("region_hints", []):
        chain.append({"clue": f"{h['script']} script in signage", "inference": h["region_hint"], "confidence": 0.3, "source": "OCR"})
    if sc.get("devanagari_language_guess", "") and sc["devanagari_language_guess"].startswith("Marathi"):
        chain.append({"clue": "Marathi-specific words/letters (e.g. ळ, आहे, च्या)", "inference": "Maharashtra (Marathi signage)",
                      "confidence": 0.4, "source": "OCR"})
        cands.append({"label": "Marathi signage", "query": "Maharashtra, India", "radius_km": RADIUS_KM["marathi"], "confidence": 0.4})

    ind = res.get("india", {})
    for p in ind.get("plates", []):
        chain.append({"clue": f"Number plate {p['plate']}", "inference": f"{p['state']} — RTO {p['rto']}: {p['rto_region']}",
                      "confidence": p["confidence"], "source": "OCR+India RTO table",
                      "caveat": "Vehicles travel; registration = owner's RTO, not photo location"})
        if p["rto_region"] and "not in curated" not in p["rto_region"] and p["rto"]:
            cands.append({"label": f"RTO {p['rto']}", "query": f"{_clean(p['rto_region'])}, {p['state']}, India",
                          "radius_km": RADIUS_KM["rto"], "confidence": p["confidence"], "region": p["rto_region"] + " " + p["state"]})
    for p in ind.get("pincodes", []):
        chain.append({"clue": f"PIN code {p['pin']}", "inference": f"{p['region']} ({p['precision']})", "confidence": p["confidence"],
                      "source": "OCR+PIN prefix table"})
        cands.append({"label": f"PIN {p['pin']}", "query": f"{p['pin']}, India", "fallback_query": f"{_clean(p['region'])}, India",
                      "radius_km": RADIUS_KM["pin3" if "3-digit" in p["precision"] else "pin2"], "confidence": p["confidence"], "region": p["region"]})
    for p in ind.get("phones", []):
        chain.append({"clue": f"Phone {p['number']}", "inference": p["region"], "confidence": p["confidence"], "source": "OCR+STD table"})
        if p["type"] == "landline":
            cands.append({"label": f"STD {p['std']}", "query": f"{_clean(p['region'])}, India", "radius_km": RADIUS_KM["std"],
                          "confidence": p["confidence"], "region": p["region"]})
    for p in ind.get("road_rail", []):
        chain.append({"clue": f"Text '{p['match']}'", "inference": p["hint"], "confidence": p["confidence"], "source": "OCR pattern"})
    for b in ind.get("brands", []):
        chain.append({"clue": f"Brand/agency '{b['brand']}'", "inference": b["region"] + " (heuristic)", "confidence": b["confidence"], "source": "curated brand list"})
        cands.append({"label": f"brand {b['brand']}", "query": f"{_clean(b['region'])}, India", "radius_km": RADIUS_KM["brand"],
                      "confidence": b["confidence"], "region": b["region"]})

    v = res.get("vision_llm", {})
    if v.get("status") == "ok":
        for r in (v["result"].get("ranked_regions") or [])[:3]:
            chain.append({"clue": "Vision-LLM environmental reading", "inference": f"{r.get('region')}, {r.get('country')}",
                          "confidence": round(min(float(r.get("confidence") or 0.2), 0.6), 2), "source": v["provider"]})
            if r.get("lat") is not None:
                cands.append({"label": "vision LLM", "lat": r["lat"], "lon": r["lon"], "radius_km": RADIUS_KM["llm"],
                              "confidence": round(min(float(r.get("confidence") or 0.2), 0.6), 2)})
    g = res.get("geoclip", {})
    if g.get("status") == "ok" and g.get("top_k"):
        t = g["top_k"][0]
        chain.append({"clue": "GeoCLIP top-1", "inference": f"{t['lat']:.3f}, {t['lon']:.3f} (p={t['p']:.3f})", "confidence": 0.25, "source": "GeoCLIP"})
        cands.append({"label": "GeoCLIP", "lat": t["lat"], "lon": t["lon"], "radius_km": RADIUS_KM["geoclip"], "confidence": 0.25})

    # agreement boost: clues whose region text shares a place token reinforce each other
    tokens = lambda c: set(re.findall(r"[a-z]{4,}", (c.get("region") or c.get("query") or "").lower())) - {"india", "district", "series"}
    for c in cands:
        agree = sum(1 for o in cands if o is not c and tokens(c) & tokens(o))
        if agree:
            c["confidence"] = round(min(c["confidence"] + 0.1 * agree, 0.85), 2)
            c["agreeing_clues"] = agree
    cands.sort(key=lambda c: (c["confidence"], -c["radius_km"]), reverse=True)
    chain.sort(key=lambda c: c["confidence"], reverse=True)
    return {"chain": chain, "candidates": cands, "integrity_flags": penalties}


def locate(ev: dict, geocode_search, offline: bool = False) -> dict | None:
    for c in ev["candidates"]:
        if "lat" in c:
            return {**c}
        for q in filter(None, [c.get("query"), c.get("fallback_query")]):
            g = geocode_search(q, offline=offline)
            if g.get("status") == "ok":
                return {**c, "lat": g["lat"], "lon": g["lon"], "geocoded_as": g["display_name"]}
    return None
