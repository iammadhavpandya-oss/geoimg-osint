"""Minimal local Flask UI. Bound to 127.0.0.1 by the CLI; uploads stay on this machine."""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from flask import Flask, abort, request, send_from_directory
from werkzeug.utils import secure_filename

PAGE = """<!doctype html><html><head><meta charset=utf-8><title>geoimg</title><style>
body{font-family:system-ui;background:#0b1120;color:#e2e8f0;max-width:760px;margin:40px auto;padding:0 20px}
.card{background:#131c31;border:1px solid #22304d;border-radius:14px;padding:22px}button{background:#22c55e;border:0;padding:10px 18px;border-radius:8px;font-weight:700}
label{display:block;margin:8px 0}a{color:#7dd3fc}</style></head><body><h1>🛰️ geoimg</h1>
<p>Educational image-geolocation OSINT. Use only on your own images, CTFs or authorised investigations.</p>
<div class=card><form method=post action="/analyze" enctype=multipart/form-data>
<input type=file name=image accept="image/*" required>
<label><input type=checkbox name=offline> offline (no Nominatim)</label>
<label><input type=checkbox name=strip> also give me a metadata-stripped copy</label>
<button>Analyse</button></form></div>{extra}</body></html>"""


def create_app(out_dir: str = "reports") -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024
    out = Path(out_dir).resolve()
    up = out / "uploads"
    up.mkdir(parents=True, exist_ok=True)

    @app.get("/")
    def index():
        return PAGE.replace("{extra}", "")

    @app.post("/analyze")
    def analyze_route():
        from .pipeline import analyze
        f = request.files.get("image")
        if not f or not f.filename:
            abort(400)
        name = f"{uuid.uuid4().hex[:8]}_{secure_filename(f.filename)}"
        path = up / name
        f.save(path)
        r = analyze(str(path), str(out), offline=bool(request.form.get("offline")))
        links = f'<p>✅ <a href="/r/{Path(r["outputs"]["html"]).name}">Open HTML report</a> · <a href="/r/{Path(r["outputs"]["json"]).name}">JSON</a> · <a href="/r/{Path(r["outputs"]["reverse_search_page"]).name}">reverse search</a></p>'
        if request.form.get("strip"):
            from .modules.strip import strip
            clean = out / f"{path.stem}_clean{path.suffix}"
            strip(str(path), str(clean))
            links += f'<p>🧹 <a href="/r/{clean.name}">metadata-stripped copy</a></p>'
        return PAGE.replace("{extra}", links)

    @app.get("/r/<path:name>")
    def report(name):
        return send_from_directory(out, name)

    return app
