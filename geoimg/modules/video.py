"""Video support: ffprobe metadata (incl. ISO6709 location tags from phones)
and ffmpeg keyframe extraction for per-frame analysis."""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess

ISO6709 = re.compile(r"([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)")


def probe(path: str) -> dict:
    if not shutil.which("ffprobe"):
        return {"status": "skipped", "reason": "ffprobe not installed"}
    r = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
                       capture_output=True, text=True)
    j = json.loads(r.stdout or "{}")
    tags = (j.get("format") or {}).get("tags", {})
    gps = None
    for k, v in tags.items():
        if "location" in k.lower():
            m = ISO6709.match(v)
            if m:
                gps = {"lat": float(m.group(1)), "lon": float(m.group(2)), "source_tag": k}
    return {"status": "ok", "duration": (j.get("format") or {}).get("duration"), "tags": tags,
            "creation_time": tags.get("creation_time"), "gps": gps}


def keyframes(path: str, out_dir: str, max_frames: int = 8) -> list[str]:
    if not shutil.which("ffmpeg"):
        return []
    os.makedirs(out_dir, exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-skip_frame", "nokey", "-i", path,
                    "-vsync", "vfr", "-frame_pts", "1", os.path.join(out_dir, "kf_%06d.jpg")], check=False)
    frames = sorted(glob.glob(os.path.join(out_dir, "kf_*.jpg")))
    if len(frames) > max_frames:  # evenly thin
        step = len(frames) / max_frames
        keep = {frames[int(i * step)] for i in range(max_frames)}
        for f in frames:
            if f not in keep:
                os.remove(f)
        frames = sorted(keep)
    return frames
