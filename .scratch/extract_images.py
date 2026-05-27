#!/usr/bin/env python3
"""Use Playwright to traverse every workshop page and download all <article> images.

Requires Playwright. Saves images to agenticai/workshop-extract/workshop-images/<page-slug>/.
Also writes a manifest.json with URL -> local path mapping per page.

Strategy:
- Open the workshop using existing logged-in browser session via the persistent profile used by
  the Playwright MCP. We'll use a separate playwright run with reuse=False to avoid conflict —
  fall back to using requests with the signed URLs (signed URLs can be downloaded by anyone
  with the URL within validity window, no auth needed).

The MCP already gave us URLs for a couple of pages. Easier: scrape every page via the MCP,
collect image URLs, then download with requests (no auth needed since URLs are pre-signed).

This file just downloads from a list of URL+alt pairs supplied via stdin JSON.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import urllib.request

BASE = Path("/Users/toule/Documents/Works/2026/교육용자료/agenticai/workshop-extract/workshop-images")


def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", s).strip("-")
    return s[:80] or "img"


def filename_from_url(url: str, alt: str) -> str:
    path = urlparse(url).path
    name = Path(unquote(path)).name
    if not name or "." not in name:
        name = slugify(alt) + ".png"
    return name


def main() -> int:
    manifest_in = json.loads(sys.stdin.read())
    # manifest_in: {"pages": [{"slug": "...", "url": "...", "images": [{src, alt}]}]}
    out_manifest: dict = {"pages": []}
    for page in manifest_in["pages"]:
        slug = page["slug"]
        page_dir = BASE / slug
        page_dir.mkdir(parents=True, exist_ok=True)
        page_entry = {"slug": slug, "url": page["url"], "images": []}
        for idx, img in enumerate(page["images"]):
            src = img["src"]
            alt = img.get("alt", "")
            fname = filename_from_url(src, alt)
            local = page_dir / f"{idx:02d}-{fname}"
            try:
                with urllib.request.urlopen(src, timeout=30) as r:  # noqa: S310
                    local.write_bytes(r.read())
                page_entry["images"].append({"alt": alt, "src": src, "local": str(local.relative_to(BASE.parent))})
                print(f"  ✓ {slug}/{local.name}")
            except Exception as e:  # noqa: BLE001
                page_entry["images"].append({"alt": alt, "src": src, "local": None, "error": str(e)})
                print(f"  ✗ {slug}/{local.name}: {e}")
        out_manifest["pages"].append(page_entry)
    (BASE / "manifest.json").write_text(json.dumps(out_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nManifest: {BASE / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
