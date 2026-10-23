"""Reverse image search helper: ready-made links (when the image has a public URL)
and manual-upload instructions. No result scraping (respects engines' ToS)."""
from __future__ import annotations

import html
from urllib.parse import quote

ENGINES = {
    "Google Lens": ("https://lens.google.com/uploadbyurl?url={u}", "https://lens.google.com/",
                    "Best for landmarks, shops, products. Click the camera icon and upload."),
    "Yandex Images": ("https://yandex.com/images/search?rpt=imageview&url={u}", "https://yandex.com/images/",
                      "Strong for faces of places/buildings & Eastern Europe/Asia; use the camera icon."),
    "Bing Visual Search": ("https://www.bing.com/images/search?view=detailv2&iss=sbi&q=imgurl:{u}",
                           "https://www.bing.com/visualsearch", "Good general coverage; drag & drop upload."),
    "TinEye (oldest first)": ("https://tineye.com/search?url={u}&sort=crawl_date&order=asc", "https://tineye.com/",
                              "Exact/near-duplicate matches. Sort by 'Oldest' to find earliest appearance."),
}


def links(public_url: str | None = None) -> list[dict]:
    out = []
    for name, (by_url, upload, tip) in ENGINES.items():
        out.append({"engine": name, "url": by_url.format(u=quote(public_url, safe="")) if public_url else None,
                    "upload_page": upload, "tip": tip})
    return out


def aggregation_page(image_name: str, thumb_b64: str | None, public_url: str | None = None) -> str:
    rows = []
    for l in links(public_url):
        btn = (f'<a class="btn" href="{html.escape(l["url"])}" target="_blank">Search by URL</a>' if l["url"] else "")
        rows.append(f'<div class="card"><h3>{l["engine"]}</h3><p>{l["tip"]}</p>{btn}'
                    f'<a class="btn alt" href="{l["upload_page"]}" target="_blank">Open upload page</a></div>')
    img = f'<img src="data:image/jpeg;base64,{thumb_b64}">' if thumb_b64 else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Reverse search - {html.escape(image_name)}</title>
<style>body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;max-width:900px;margin:auto;padding:24px}}
.card{{background:#1e293b;border-radius:12px;padding:14px 18px;margin:12px 0}}.btn{{display:inline-block;background:#22c55e;color:#04210f;
padding:8px 14px;border-radius:8px;text-decoration:none;margin-right:8px;font-weight:600}}.alt{{background:#38bdf8}}
img{{max-width:280px;border-radius:10px}}</style></head><body><h1>Reverse image search: {html.escape(image_name)}</h1>{img}
<p>Local files cannot be sent by link: open each upload page and drag the image in. Results are NOT scraped.
<b>Earliest appearance:</b> on TinEye choose <i>Sort: Oldest</i>; on Google use <i>Tools &rarr; time range</i> on the 'Exact matches' tab.</p>
{''.join(rows)}</body></html>"""
