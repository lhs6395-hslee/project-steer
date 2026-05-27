#!/usr/bin/env python3
"""Download all workshop page images using the URLs collected via Playwright.

Reads JSON from stdin (the array returned by browser_evaluate).
Saves to /Users/toule/.../agenticai/workshop-extract/workshop-images/<slug>/.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlparse

BASE = Path("/Users/toule/Documents/Works/2026/교육용자료/agenticai/workshop-extract/workshop-images")


def slug_path_segment(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", s).strip("-")[:80] or "page"


def filename_from_url(url: str, alt: str, idx: int) -> str:
    path = urlparse(url).path
    name = Path(unquote(path)).name
    if not name or "." not in name:
        name = slug_path_segment(alt or f"img-{idx}") + ".png"
    return f"{idx:02d}-{name}"


def main() -> int:
    data = json.loads(sys.stdin.read())
    manifest: dict = {"pages": []}
    for page in data:
        slug = page["slug"]
        # Build directory path mirroring slug
        dir_segments = [slug_path_segment(p) for p in slug.split("/")]
        page_dir = BASE / "/".join(dir_segments)
        page_dir.mkdir(parents=True, exist_ok=True)
        page_entry = {"slug": slug, "dir": str(page_dir.relative_to(BASE.parent)), "images": []}
        for idx, img in enumerate(page["images"]):
            src = img["src"]
            alt = img.get("alt", "")
            fname = filename_from_url(src, alt, idx)
            local = page_dir / fname
            try:
                req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
                    local.write_bytes(r.read())
                page_entry["images"].append({
                    "alt": alt,
                    "filename": fname,
                    "size": local.stat().st_size,
                })
                print(f"  ✓ {slug}/{fname} ({local.stat().st_size:,} bytes)")
            except Exception as e:  # noqa: BLE001
                page_entry["images"].append({"alt": alt, "src": src, "error": str(e)})
                print(f"  ✗ {slug}/{fname}: {e}")
        manifest["pages"].append(page_entry)

    (BASE / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    total = sum(1 for p in manifest["pages"] for i in p["images"] if "filename" in i)
    print(f"\nTotal downloaded: {total}")
    print(f"Manifest: {BASE / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
