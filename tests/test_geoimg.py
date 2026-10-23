import datetime as dt
import json
import os
import shutil
import subprocess

import pytest
from PIL import Image

from geoimg.modules import (evidence, geocode, geoclip_mod, india, manipulation, metadata, ocr, overpass,
                            reverse_search, strip, sun, verify_links, video, vision_llm)

NET = os.environ.get("GEOIMG_NET") == "1"
HAS_TESS = bool(shutil.which("tesseract"))


# ---------- metadata ----------
def test_dms_to_decimal():
    assert metadata.dms_to_decimal(((18, 1), (55, 1), (192, 10)), "N") == pytest.approx(18.922, abs=1e-4)
    assert metadata.dms_to_decimal((72, 50, 4.92), "W") == pytest.approx(-72.8347, abs=1e-4)
    assert metadata.dms_to_decimal(metadata.decimal_to_dms_rational(72.8347), "E") == pytest.approx(72.8347, abs=1e-6)


@pytest.mark.parametrize("force_pillow", [False, True])
def test_gps_extraction(samples, monkeypatch, force_pillow):
    if force_pillow:
        monkeypatch.setattr(metadata, "_exiftool", lambda p: None)
    md = metadata.extract(str(samples / "gateway_gps.jpg"))
    assert md["engine"] == ("pillow" if force_pillow else ("exiftool" if shutil.which("exiftool") else "pillow"))
    assert md["gps"]["lat"] == pytest.approx(18.9220, abs=1e-4)
    assert md["gps"]["lon"] == pytest.approx(72.8347, abs=1e-4)
    assert md["gps"]["alt"] == pytest.approx(10.0)
    assert md["summary"]["Make"] == "geoimg-test"
    assert str(md["timestamp"]).startswith("2026:01:26")


def test_no_gps(samples):
    assert metadata.extract(str(samples / "signboard_nogps.jpg"))["gps"] is None


def test_thumbnail_mismatch(samples):
    assert metadata.thumbnail_check(str(samples / "gateway_gps.jpg"))["mismatch"] is False
    t = metadata.thumbnail_check(str(samples / "tampered_gps.jpg"))
    assert t["mismatch"] is True and "possible edit" in t["note"]


# ---------- geocode ----------
def test_geocode_offline_and_links():
    assert geocode.reverse(18.922, 72.8347, offline=True)["status"] == "skipped"
    l = geocode.links(18.922, 72.8347)
    assert "18.922,72.8347" in l["google_maps"] and "openstreetmap.org" in l["osm"]


def test_geocode_network_failure_graceful(monkeypatch):
    import requests

    def boom(*a, **k):
        raise requests.ConnectionError("no network")
    monkeypatch.setattr(requests, "get", boom)
    r = geocode.reverse(18.922, 72.8347)
    assert r["status"] == "error" and "Nominatim unavailable" in r["reason"]


@pytest.mark.skipif(not NET, reason="set GEOIMG_NET=1 for live Nominatim test")
def test_geocode_live():
    r = geocode.reverse(18.9220, 72.8347)
    assert r["status"] == "ok" and "Mumbai" in r["display_name"]
    assert geocode.reverse(18.9220, 72.8347)["cached"] is True


# ---------- OCR / scripts ----------
def test_script_detection():
    s = ocr.detect_scripts("श्री गणेश स्टोअर्स आमच्या येथे सेवा आहे  શ્રી ગણેશ સ્ટોર્સ Shop")
    assert {"Devanagari", "Gujarati", "Latin"} <= set(s["counts"])
    assert s["devanagari_language_guess"].startswith("Marathi")
    assert ocr.detect_scripts("यह दुकान में है और")["devanagari_language_guess"] == "Hindi"


@pytest.mark.skipif(not HAS_TESS, reason="tesseract not installed")
def test_ocr_signboard(samples):
    r = ocr.run(str(samples / "signboard_nogps.jpg"))
    assert r["status"] == "ok"
    assert "GANESH" in r["text"].upper()
    assert "401202" in r["text"]
    assert r["scripts"]["counts"].get("Devanagari", 0) > 10
    if "guj" in r["langs"]:
        assert r["scripts"]["counts"].get("Gujarati", 0) > 5


@pytest.mark.skipif(not HAS_TESS, reason="tesseract not installed")
def test_ocr_noise_filtered(samples):
    assert ocr.run(str(samples / "gateway_gps.jpg"))["text"] == ""


# ---------- India ----------
def test_india_heuristics():
    r = india.analyze("MH 48 AB 1234  MH-04-CD-9999  24 BH 1234 AA  Vasai 401202  Tel 0250 2321234 "
                      "+91 98200 12345  NH 48  VIRAR 12 km  Aarey milk  Platform No. 3")
    plates = {p["rto"]: p for p in r["plates"]}
    assert "Vasai" in plates["MH-48"]["rto_region"] and "Thane" in plates["MH-04"]["rto_region"]
    assert any("Bharat" in p["state"] for p in r["plates"])
    assert r["pincodes"][0]["region"].startswith("Thane/Palghar")
    assert any(p.get("std") == "0250" for p in r["phones"])
    assert any(p["type"] == "mobile" and p["confidence"] <= 0.1 for p in r["phones"])
    hints = " ".join(x["hint"] for x in r["road_rail"])
    assert "National Highway 48" in hints and "VIRAR 12 km" in hints and "platform 3" in hints.lower()
    assert r["brands"][0]["brand"] == "aarey"


def test_pin_two_digit_fallback():
    assert india.pincodes("PIN 682001")[0]["region"] == "Kerala"


# ---------- manipulation ----------
def test_manipulation(samples, tmp_path):
    md = metadata.extract(str(samples / "tampered_gps.jpg"))
    m = manipulation.run(str(samples / "tampered_gps.jpg"), md, str(tmp_path / "ela.png"))
    assert os.path.exists(m["ela"]["ela_image"])
    assert m["clone"]["flag"] is True
    clean = manipulation.clone_detect(str(samples / "gateway_gps.jpg"))
    assert clean["flag"] is False
    assert manipulation.clone_detect(str(samples / "signboard_nogps.jpg"))["flag"] is False  # repeated text != clone


def test_ai_heuristic(tmp_path):
    from PIL.PngImagePlugin import PngInfo
    p = tmp_path / "gen.png"
    info = PngInfo()
    info.add_text("parameters", "a temple at sunset, Steps: 30, Sampler: Euler")
    Image.new("RGB", (512, 512), "gray").save(p, pnginfo=info)
    r = manipulation.ai_heuristic(str(p), metadata.extract(str(p)))
    assert r["ai_likelihood"] >= 0.5 and "LOW-CONFIDENCE" in r["label"]


# ---------- overpass / links ----------
def test_overpass_builder():
    f = overpass.clues_from_text("Petrol Pump near Vasai Road Railway Station, Shree Ram Mandir")
    labels = [l for _, l in f]
    assert labels[:3] == ["fuel station", "railway station", "Hindu temple"]
    q = overpass.build(f, around=(19.38, 72.83, 5000))
    assert q["status"] == "ok" and '["amenity"="fuel"](around:5000,19.38,72.83)' in q["query"]
    assert "around.c1:50" in q["query"] and q["overpass_turbo"].startswith("https://overpass-turbo.eu/?Q=")
    assert overpass.build([])["status"] == "skipped"
    assert 'area["name"="Vasai-Virar"]' in overpass.build(f, area="Vasai-Virar")["query"]


def test_reverse_and_verify_links(tmp_path):
    ls = reverse_search.links("https://example.org/a.jpg")
    names = [l["engine"] for l in ls]
    assert names == ["Google Lens", "Yandex Images", "Bing Visual Search", "TinEye (oldest first)"]
    assert "sort=crawl_date&order=asc" in ls[3]["url"]
    assert all(l["url"] is None for l in reverse_search.links())
    assert "TinEye" in reverse_search.aggregation_page("x.jpg", None)
    v = verify_links.links(18.922, 72.8347)
    assert "wayback" in v["Esri Wayback (historical)"] and "sentinel-hub" in v["Sentinel Hub EO Browser"]
    assert verify_links.mapillary_nearby(18.922, 72.8347)["status"] == "skipped"


# ---------- sun ----------
def test_sun_consistency():
    # Mumbai, 26 Jan 2026 16:30 IST -> sun in WSW (~238°), shadows point ~58°
    t = dt.datetime(2026, 1, 26, 11, 0, tzinfo=dt.timezone.utc)
    ok = sun.analyze(t, shadow_azimuth=58, lat=18.922, lon=72.8347)
    assert ok["candidate"]["consistent"] is True
    bad = sun.analyze(t, shadow_azimuth=240, lat=18.922, lon=72.8347)
    assert bad["candidate"]["consistent"] is False
    scan = sun.analyze(dt.datetime(2026, 3, 20, 6, 50, tzinfo=dt.timezone.utc), shadow_ratio=0.02, lon=72.8)
    assert abs(scan["latitude_scan"]["best"][0]["lat"]) < 10  # near-vertical sun at equinox noon -> near equator


# ---------- optional AI modules ----------
def test_vision_llm_skips_without_key(samples):
    assert vision_llm.run(str(samples / "gateway_gps.jpg"))["status"] == "skipped"


def test_vision_llm_mocked(samples, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-real")

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"content": [{"type": "text", "text": json.dumps({"driving_side": "left", "reasoning": "monsoon flora",
                     "ranked_regions": [{"region": "Mumbai", "country": "India", "confidence": 0.5, "lat": 18.9, "lon": 72.8}]})}]}

    class S:
        def post(self, url, **kw):
            assert "anthropic" in url and kw["headers"]["x-api-key"] == "test-not-real"
            return R()
    r = vision_llm.run(str(samples / "gateway_gps.jpg"), session=S())
    assert r["status"] == "ok" and r["result"]["driving_side"] == "left"


def test_geoclip_skip_without_install(monkeypatch, samples):
    monkeypatch.setattr(geoclip_mod, "_python", lambda: None)
    assert geoclip_mod.run(str(samples / "gateway_gps.jpg"))["status"] == "skipped"


def test_geoclip_heatmap(tmp_path):
    p = geoclip_mod.heatmap_png([{"lat": 18.9, "lon": 72.8, "p": 0.5}, {"lat": 48, "lon": 2, "p": 0.1}], str(tmp_path / "h.png"))
    assert Image.open(p).size == (1024, 512)


# ---------- privacy strip ----------
def test_strip_all_and_gps_only(samples, tmp_path):
    src = str(samples / "gateway_gps.jpg")
    out = tmp_path / "clean.jpg"
    strip.strip(src, str(out))
    md = metadata.extract(str(out))
    assert md["gps"] is None and "Make" not in md["summary"]
    out2 = tmp_path / "gpsless.jpg"
    strip.strip(src, str(out2), gps_only=True)
    md2 = metadata.extract(str(out2))
    assert md2["gps"] is None and md2["summary"]["Make"] == "geoimg-test"


# ---------- video ----------
@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg missing")
def test_video_keyframes(samples, tmp_path):
    v = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-t", "3", "-i", str(samples / "signboard_nogps.jpg"),
                    "-vf", "scale=700:-2", "-r", "10", "-g", "10", "-pix_fmt", "yuv420p",
                    "-metadata", "location=+19.3919+072.8397/", "-movflags", "+use_metadata_tags", str(v)], check=True)
    info = video.probe(str(v))
    assert info["status"] == "ok"
    frames = video.keyframes(str(v), str(tmp_path / "frames"), max_frames=2)
    assert 1 <= len(frames) <= 2
    if info["gps"]:
        assert info["gps"]["lat"] == pytest.approx(19.3919)


# ---------- evidence + end-to-end ----------
def test_evidence_penalises_tampering():
    res = {"metadata": {"gps": {"lat": 1, "lon": 2}, "summary": {"Software": "Adobe Photoshop"}, "thumbnail": {"mismatch": True}},
           "manipulation": {"ai": {"ai_likelihood": 0}, "clone": {"flag": False}}}
    ev = evidence.build(res)
    assert ev["chain"][0]["confidence"] == pytest.approx(0.6)
    assert len(ev["integrity_flags"]) == 2


@pytest.mark.skipif(not HAS_TESS, reason="tesseract not installed")
def test_pipeline_end_to_end(samples, tmp_path, monkeypatch):
    from geoimg.pipeline import analyze
    # offline: no network; region pin falls back to cached/none
    r = analyze(str(samples / "gateway_gps.jpg"), str(tmp_path), offline=True)
    assert r["location"]["label"] == "EXIF GPS" and r["location"]["confidence"] == 0.9
    assert r["geocode"]["status"] == "skipped"
    html = open(r["outputs"]["html"]).read()
    assert "Leaflet" in html or "leaflet" in html
    assert "18.92200" in html and "IT Act" in html
    json.load(open(r["outputs"]["json"]))
    # no-GPS signboard: India module must drive the inference (forward geocode mocked)
    monkeypatch.setattr(geocode, "search", lambda q, offline=False: {"status": "ok", "lat": 19.42, "lon": 72.82, "display_name": q})
    r2 = analyze(str(samples / "signboard_nogps.jpg"), str(tmp_path), offline=True)
    assert r2["metadata"]["gps"] is None
    assert r2["location"]["label"].startswith(("RTO MH-48", "PIN 401202", "STD 0250"))
    assert r2["location"]["confidence"] >= 0.6
    assert r2["overpass"]["status"] == "ok"
    t = analyze(str(samples / "tampered_gps.jpg"), str(tmp_path), offline=True)
    assert "embedded thumbnail mismatch" in t["evidence"]["integrity_flags"]
    assert t["location"]["confidence"] < 0.9


def test_cli_strip_and_web(samples, tmp_path):
    from geoimg.cli import main
    out = tmp_path / "c.jpg"
    assert main(["strip", str(samples / "gateway_gps.jpg"), "-o", str(out)]) == 0
    assert metadata.extract(str(out))["gps"] is None
    assert main(["web", "--host", "0.0.0.0"]) == 2  # refuses non-loopback
    from geoimg.web import create_app
    c = create_app(str(tmp_path / "web")).test_client()
    assert b"geoimg" in c.get("/").data
