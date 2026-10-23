"""OCR via tesseract (eng + hin + mar + guj when packs are installed) and
Unicode-script detection with a Hindi-vs-Marathi heuristic."""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile

from PIL import Image, ImageOps

WANTED_LANGS = ["eng", "hin", "mar", "guj"]

SCRIPTS = {
    "Devanagari": (0x0900, 0x097F), "Bengali": (0x0980, 0x09FF), "Gurmukhi": (0x0A00, 0x0A7F),
    "Gujarati": (0x0A80, 0x0AFF), "Odia": (0x0B00, 0x0B7F), "Tamil": (0x0B80, 0x0BFF),
    "Telugu": (0x0C00, 0x0C7F), "Kannada": (0x0C80, 0x0CFF), "Malayalam": (0x0D00, 0x0D7F),
    "Arabic/Urdu": (0x0600, 0x06FF),
}
SCRIPT_REGION = {
    "Devanagari": "North/Central/West India (Hindi belt, Maharashtra, Nepal)",
    "Gujarati": "Gujarat (or Gujarati diaspora shops, e.g. Mumbai)",
    "Bengali": "West Bengal / Tripura / Assam (Bangladesh)", "Gurmukhi": "Punjab",
    "Odia": "Odisha", "Tamil": "Tamil Nadu / Puducherry (Sri Lanka)", "Telugu": "Andhra Pradesh / Telangana",
    "Kannada": "Karnataka", "Malayalam": "Kerala", "Arabic/Urdu": "Urdu signage (J&K, Hyderabad, UP) or Gulf/Pakistan",
}
MARATHI_MARKERS = ["ळ", "आहे", "आणि", "च्या", "ची ", "चे ", "महाराष्ट्र", "मुंबई", "नगर परिषद", "महानगरपालिका", "शाळा"]
HINDI_MARKERS = ["है", "और", "का ", "की ", "के ", "में", "नहीं", "दुकान", "भंडार"]


def available_langs() -> list[str]:
    if not shutil.which("tesseract"):
        return []
    out = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout
    have = {l.strip() for l in out.splitlines()[1:]}
    return [l for l in WANTED_LANGS if l in have]


def detect_scripts(text: str) -> dict:
    counts = {"Latin": 0}
    for ch in text:
        cp = ord(ch)
        if ch.isascii() and ch.isalpha():
            counts["Latin"] += 1
            continue
        for name, (lo, hi) in SCRIPTS.items():
            if lo <= cp <= hi:
                counts[name] = counts.get(name, 0) + 1
                break
    counts = {k: v for k, v in counts.items() if v}
    hints = []
    for s in counts:
        if s in SCRIPT_REGION and counts[s] >= 8:  # ignore a few stray glyphs
            hints.append({"script": s, "region_hint": SCRIPT_REGION[s]})
    lang_guess = None
    if counts.get("Devanagari"):
        m = sum(text.count(w) for w in MARATHI_MARKERS)
        h = sum(text.count(w) for w in HINDI_MARKERS)
        lang_guess = "Marathi (Maharashtra)" if m > h else ("Hindi" if h > m else "Devanagari (Hindi/Marathi undetermined)")
    return {"counts": counts, "region_hints": hints, "devanagari_language_guess": lang_guess}


def _prep(path: str) -> str:
    with Image.open(path) as im:
        g = ImageOps.grayscale(ImageOps.exif_transpose(im))
        if max(g.size) < 1600:
            f = 1600 / max(g.size)
            g = g.resize((int(g.width * f), int(g.height * f)))
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        g.save(tmp.name)
        return tmp.name


def run(path: str, min_conf: float = 60.0) -> dict:
    langs = available_langs()
    if not langs:
        return {"status": "skipped", "reason": "tesseract not installed (apt install tesseract-ocr tesseract-ocr-hin tesseract-ocr-mar tesseract-ocr-guj)", "text": ""}
    pre = _prep(path)
    seen, lines, confs = set(), [], []
    for psm in ("11", "6"):  # sparse text (signboards) and uniform block
        r = subprocess.run(["tesseract", pre, "stdout", "-l", "+".join(langs), "--psm", psm, "tsv"],
                           capture_output=True, text=True, timeout=180)
        groups: dict = {}
        for row in r.stdout.splitlines()[1:]:
            c = row.split("\t")
            if len(c) < 12 or not c[11].strip():
                continue
            try:
                conf = float(c[10])
            except ValueError:
                continue
            if conf < min_conf:  # drop low-confidence noise (textures, foliage)
                continue
            groups.setdefault((c[2], c[3], c[4]), []).append(c[11].strip())
            confs.append(conf)
        for words in groups.values():
            ln = re.sub(r"\s+", " ", " ".join(words)).strip()
            # texture noise looks like "ણ ણ = wh": many 1-char tokens. Require >=4 alnum chars
            # and an average token length >= 2.
            toks = [t for t in (re.sub(r"[\W_]", "", w) for w in words) if t]
            ok = toks and sum(map(len, toks)) >= 4 and sum(map(len, toks)) / len(toks) >= 2
            if ok and ln.lower() not in seen:
                seen.add(ln.lower())
                lines.append(ln)
    text = "\n".join(lines)
    return {"status": "ok", "langs": langs, "min_conf": min_conf, "mean_word_conf": round(sum(confs) / len(confs), 1) if confs else None,
            "text": text, "lines": lines, "scripts": detect_scripts(text)}
