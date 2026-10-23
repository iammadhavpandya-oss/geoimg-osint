"""Sun/shadow consistency (SunCalc-style, via astral).

Given a UTC datetime and a measured shadow azimuth (degrees clockwise from true
north, direction the shadow POINTS) and optionally shadow_length/object_height,
compute the sun position and either check a candidate location or scan
latitudes for consistent positions."""
from __future__ import annotations

import math
from datetime import datetime, timezone


def _sun(lat: float, lon: float, dt: datetime):
    from astral import Observer
    from astral.sun import azimuth, elevation
    obs = Observer(latitude=lat, longitude=lon)
    return azimuth(obs, dt), elevation(obs, dt)


def analyze(dt: datetime, shadow_azimuth: float | None = None, shadow_ratio: float | None = None,
            lat: float | None = None, lon: float | None = None) -> dict:
    try:
        import astral  # noqa: F401
    except ImportError:
        return {"status": "skipped", "reason": "astral not installed"}
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    exp_sun_az = (shadow_azimuth + 180) % 360 if shadow_azimuth is not None else None
    exp_el = math.degrees(math.atan(1 / shadow_ratio)) if shadow_ratio else None
    res = {"status": "ok", "datetime_utc": dt.astimezone(timezone.utc).isoformat(),
           "expected_sun_azimuth": exp_sun_az, "expected_sun_elevation": round(exp_el, 2) if exp_el else None}
    if lat is not None and lon is not None:
        az, el = _sun(lat, lon, dt)
        res["candidate"] = {"lat": lat, "lon": lon, "sun_azimuth": round(az, 2), "sun_elevation": round(el, 2)}
        issues = []
        if el < 0:
            issues.append("sun below horizon at this time/place but image shows shadows")
        if exp_sun_az is not None:
            d = abs((az - exp_sun_az + 180) % 360 - 180)
            res["candidate"]["azimuth_error"] = round(d, 1)
            if d > 25:
                issues.append(f"shadow direction off by {d:.0f}°")
        if exp_el is not None:
            d = abs(el - exp_el)
            res["candidate"]["elevation_error"] = round(d, 1)
            if d > 10:
                issues.append(f"shadow length implies elevation off by {d:.0f}°")
        res["candidate"]["consistent"] = not issues
        res["candidate"]["issues"] = issues
    if exp_sun_az is not None or exp_el is not None:
        scan_lon = lon if lon is not None else 78.0
        best = []
        for i in range(-120, 121):
            la = i * 0.5
            az, el = _sun(la, scan_lon, dt)
            if el <= 0:
                continue
            err = 0.0
            if exp_sun_az is not None:
                err += abs((az - exp_sun_az + 180) % 360 - 180)
            if exp_el is not None:
                err += abs(el - exp_el)
            best.append((err, la, az, el))
        best.sort()
        res["latitude_scan"] = {"longitude_used": scan_lon,
                                "best": [{"lat": b[1], "err": round(b[0], 1), "sun_az": round(b[2], 1), "sun_el": round(b[3], 1)} for b in best[:5]],
                                "note": "Longitude fixed (candidate or 78°E India default); timestamp accuracy is critical."}
    return res
