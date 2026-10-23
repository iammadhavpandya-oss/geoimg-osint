"""Optional vision-LLM geolocation estimate. Enabled only when an API key env var
is set: ANTHROPIC_API_KEY or OPENAI_API_KEY (no keys are stored in code).
Model names are configurable via GEOIMG_ANTHROPIC_MODEL / GEOIMG_OPENAI_MODEL."""
from __future__ import annotations

import base64
import io
import json
import os
import re

from PIL import Image

PROMPT = """You are assisting an authorized, educational OSINT geolocation exercise.
Analyse ONLY environmental/visual clues in this image (do not identify people).
Consider: vegetation & climate, road markings & lane colours, driving side, kerb/bollard styles,
utility poles & wiring, architecture & roofing, signage language/script, vehicle types & plates,
terrain, sun position. Extra context from automated OCR/metadata: {context}
Respond with ONLY JSON: {{"clues": [{{"clue": str, "inference": str}}], "driving_side": "left|right|unknown",
"ranked_regions": [{{"region": str, "country": str, "confidence": 0-1, "lat": float|null, "lon": float|null}}],
"reasoning": str}}"""


def _b64(path: str) -> str:
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((1280, 1280))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def provider() -> str | None:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return None


def _parse(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)) if m else {"raw": text}
    except json.JSONDecodeError:
        return {"raw": text}


def run(path: str, context: str = "", session=None) -> dict:
    prov = provider()
    if not prov:
        return {"status": "skipped", "reason": "no ANTHROPIC_API_KEY / OPENAI_API_KEY set"}
    import requests
    s = session or requests
    img = _b64(path)
    prompt = PROMPT.format(context=context[:1500] or "none")
    try:
        if prov == "anthropic":
            r = s.post("https://api.anthropic.com/v1/messages", timeout=90, headers={
                "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                "content-type": "application/json"}, json={
                "model": os.environ.get("GEOIMG_ANTHROPIC_MODEL", "claude-sonnet-4-5"), "max_tokens": 1200,
                "messages": [{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img}},
                    {"type": "text", "text": prompt}]}]})
            r.raise_for_status()
            text = "".join(b.get("text", "") for b in r.json().get("content", []))
        else:
            r = s.post("https://api.openai.com/v1/chat/completions", timeout=90, headers={
                "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"}, json={
                "model": os.environ.get("GEOIMG_OPENAI_MODEL", "gpt-4o"), "max_tokens": 1200,
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}}]}]})
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return {"status": "error", "provider": prov, "reason": str(e)[:300]}
    return {"status": "ok", "provider": prov, "result": _parse(text),
            "note": "LLM output is a hypothesis; verify with street-level/satellite imagery."}
