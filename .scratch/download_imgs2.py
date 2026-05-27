#!/usr/bin/env python3
"""Download all workshop images using a single shared signed URL policy.

Reads from .scratch/img-paths.json (manifest of pages and image filenames).
Downloads each <base>/<filename>?<policy_qs> into agenticai/workshop-extract/workshop-images/<slug>/.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
MANIFEST = PROJECT / ".scratch" / "img-paths.json"
OUT_BASE = Path(
    "/Users/toule/Documents/Works/2026/교육용자료/agenticai/workshop-extract/workshop-images"
)


def safe_segment(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", s).strip("-")[:80] or "page"


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    base = data["base"]
    qs = data["policy_qs"]
    out_manifest: list[dict] = []
    total_ok = 0
    total_err = 0
    for page in data["pages"]:
        slug = page["slug"]
        if not page["images"]:
            continue
        page_dir = OUT_BASE / "/".join(safe_segment(p) for p in slug.split("/"))
        page_dir.mkdir(parents=True, exist_ok=True)
        page_entry = {"slug": slug, "dir": str(page_dir.relative_to(OUT_BASE.parent)), "images": []}
        for idx, img in enumerate(page["images"]):
            fn = img["name"]
            url = f"{base}/{fn}?{qs}"
            local = page_dir / f"{idx:02d}-{fn}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
                    local.write_bytes(r.read())
                size = local.stat().st_size
                page_entry["images"].append({
                    "alt": img["alt"],
                    "filename": local.name,
                    "size": size,
                })
                total_ok += 1
                print(f"  ✓ {slug}/{local.name} ({size:,})")
            except Exception as e:  # noqa: BLE001
                page_entry["images"].append({"alt": img["alt"], "filename": local.name, "error": str(e)})
                total_err += 1
                print(f"  ✗ {slug}/{local.name}: {e}")
        out_manifest.append(page_entry)
    summary = {
        "ok": total_ok,
        "err": total_err,
        "pages": out_manifest,
    }
    (OUT_BASE / "manifest.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nTotal OK: {total_ok}, errors: {total_err}")
    print(f"Manifest: {OUT_BASE / 'manifest.json'}")
    return 0 if total_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
