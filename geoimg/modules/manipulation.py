"""Manipulation checks: Error Level Analysis, ORB self-match clone detection,
and a LOW-CONFIDENCE AI-generated-image heuristic. None of these are proof."""
from __future__ import annotations

import io

from PIL import Image, ImageChops, ImageEnhance

AI_SOFTWARE_MARKERS = ["stable diffusion", "midjourney", "dall-e", "dall·e", "firefly", "novelai",
                       "comfyui", "automatic1111", "invokeai", "imagen", "gemini", "openai", "c2pa", "trainedalgorithmicmedia"]


def ela(path: str, out_path: str, quality: int = 90) -> dict:
    with Image.open(path) as im:
        orig = im.convert("RGB")
    buf = io.BytesIO()
    orig.save(buf, "JPEG", quality=quality)
    buf.seek(0)
    resaved = Image.open(buf)
    diff = ImageChops.difference(orig, resaved)
    extrema = diff.getextrema()
    max_diff = max(e[1] for e in extrema) or 1
    scale = 255.0 / max_diff
    ImageEnhance.Brightness(diff).enhance(scale).save(out_path)
    gray = diff.convert("L")
    hist = gray.histogram()
    total = sum(hist)
    mean = sum(i * c for i, c in enumerate(hist)) / total
    return {"status": "ok", "ela_image": out_path, "quality": quality, "max_diff": max_diff,
            "mean_error": round(mean, 3),
            "note": "Bright, sharply bounded regions that differ from the rest MAY indicate local edits. "
                    "Recompressed/screenshot images give noisy ELA; interpret visually."}


def clone_detect(path: str, min_dist: int = 40, ratio: float = 0.6) -> dict:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {"status": "skipped", "reason": "opencv-python-headless not installed"}
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return {"status": "skipped", "reason": "unreadable by OpenCV"}
    if max(img.shape) > 1600:
        f = 1600 / max(img.shape)
        img = cv2.resize(img, None, fx=f, fy=f)
    orb = cv2.ORB_create(nfeatures=3000)
    kps, des = orb.detectAndCompute(img, None)
    if des is None or len(kps) < 10:
        return {"status": "ok", "keypoints": len(kps or []), "suspicious_pairs": 0, "flag": False,
                "note": "too few keypoints for clone analysis"}
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    matches = bf.knnMatch(des, des, k=3)
    pairs = []
    for m in matches:
        if len(m) < 3:
            continue
        a, b = m[1], m[2]  # m[0] is the keypoint matching itself
        if a.distance < ratio * max(b.distance, 1) and a.distance < 40:
            p1 = np.array(kps[a.queryIdx].pt)
            p2 = np.array(kps[a.trainIdx].pt)
            if np.linalg.norm(p1 - p2) > min_dist:
                pairs.append((tuple(map(int, p1)), tuple(map(int, p2))))
    # count consistent displacement vectors (copy-move shifts a block by one offset)
    vecs = {}
    for p1, p2 in pairs:
        v = ((p2[0] - p1[0]) // 10, (p2[1] - p1[1]) // 10)
        if v[0] < 0 or (v[0] == 0 and v[1] < 0):
            v = (-v[0], -v[1])
        vecs[v] = vecs.get(v, 0) + 1
    top = max(vecs.values()) if vecs else 0
    # copy-move shifts a whole block by ONE offset -> one dominant cluster. Repeated text/texture
    # produces many small clusters, so also require the cluster to dominate the matches.
    flag = top >= 10 and top >= 0.25 * len(pairs)
    return {"status": "ok", "keypoints": len(kps), "suspicious_pairs": len(pairs), "largest_shift_cluster": top,
            "flag": flag, "note": ("possible copy-move region (many keypoints share one displacement)" if flag else
                                   "no strong copy-move signal") + "; repetitive textures cause false positives."}


def ai_heuristic(path: str, metadata: dict) -> dict:
    reasons, score = [], 0.0
    raw = {k.lower(): str(v).lower() for k, v in (metadata.get("raw") or {}).items()}
    blob = " ".join(list(raw.keys()) + list(raw.values()))
    for mk in AI_SOFTWARE_MARKERS:
        if mk in blob:
            reasons.append(f"metadata mentions '{mk}'")
            score += 0.5
            break
    with Image.open(path) as im:
        w, h = im.size
        info = {k.lower(): str(v).lower() for k, v in im.info.items() if isinstance(v, (str, bytes))}
    if "parameters" in info or "prompt" in info:
        reasons.append("PNG text chunk with generation parameters/prompt")
        score += 0.5
    summ = metadata.get("summary", {})
    if not summ.get("Make") and not summ.get("Model"):
        reasons.append("no camera make/model (also true for screenshots / stripped images)")
        score += 0.1
    if w % 64 == 0 and h % 64 == 0 and max(w, h) <= 2048:
        reasons.append(f"dimensions {w}x{h} are multiples of 64 (common for diffusion models)")
        score += 0.15
    score = min(score, 0.95)
    return {"status": "ok", "ai_likelihood": round(score, 2), "reasons": reasons,
            "label": "LOW-CONFIDENCE HEURISTIC - not a detector. Absence of signals proves nothing."}


def run(path: str, metadata: dict, ela_out: str) -> dict:
    return {"ela": ela(path, ela_out), "clone": clone_detect(path), "ai": ai_heuristic(path, metadata)}
