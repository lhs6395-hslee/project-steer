#!/usr/bin/env python3
"""Fix model IDs across all Confluence pages — add 'us.' prefix to Sonnet 4.6 / Haiku 4.5.

Reads each page's storage body, replaces specific bare model IDs with the
us-prefix inference profile equivalents, and writes back via REST API.

Reason: 4세대 Anthropic 모델 (sonnet-4-6, haiku-4-5-...) 은 Bedrock 에서
on-demand 직접 호출 불가 — `us.` 또는 `global.` prefix inference profile
필수. 위키 디폴트가 prefix 없는 형태로 들어가 있어 실 호출 시 실패.

근거: 본인 계정 us-west-2 직접 호출 검증 (find_callable_4gen.py).
"""
from __future__ import annotations
import os, json, sys
from base64 import b64encode
import urllib.request, urllib.error

BASE = "https://toule.atlassian.net/wiki"
EMAIL = os.environ["CONFLUENCE_EMAIL"]
TOKEN = os.environ["CONFLUENCE_API_TOKEN"]

PAGE_IDS = [
    "909770754",   # 루트 (v5)
    "910098434",   # Bootstrap (v3)
    "909901826",   # Lab-1
    "909934594",   # Lab-2
    "909869090",   # Lab-3
    "909869118",   # Lab-4
    "910295051",   # Lab-5
    "910360578",   # Lab-6
    "910163970",   # Summary
    "910622722",   # Lab-7
    "910884866",   # Lab-8
    "910753812",   # Lab-9
    "910983170",   # Lab-10
    "911048706",   # Lab-11
]

# 정확한 토큰 단위로만 치환 — 이미 prefix 있는 건 건드리지 않음.
REPLACEMENTS = [
    # bare → us. prefix
    ("anthropic.claude-sonnet-4-6", "us.anthropic.claude-sonnet-4-6"),
    ("anthropic.claude-haiku-4-5-20251001-v1:0", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
    ("anthropic.claude-opus-4-7", "us.anthropic.claude-opus-4-7"),
]


def auth_header() -> str:
    return "Basic " + b64encode(f"{EMAIL}:{TOKEN}".encode()).decode()


def request(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": auth_header(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body_txt[:500]}") from None


def fix_one(page_id: str) -> dict:
    page = request("GET", f"/rest/api/content/{page_id}?expand=body.storage,version,space")
    body = page["body"]["storage"]["value"]
    title = page["title"]
    version = page["version"]["number"]

    new_body = body
    counts = {}
    for old, new in REPLACEMENTS:
        # Already-prefixed protection: count current occurrences before swap
        bare_count = new_body.count(old)
        # 단순 치환은 위험 — "us.anthropic.claude-sonnet-4-6" 안의 substring 까지 잡힘.
        # 따라서 prefix-aware 치환: "us." 또는 "global." 가 앞에 있는 경우는 건드리지 않음.
        # 가장 단순한 안전장치: old 가 들어간 부분의 직전 4글자를 검사.
        # 더 깔끔하게는 정규식 (?<![a-zA-Z.])(old) 패턴.
        import re
        pattern = re.compile(r"(?<![a-zA-Z\.])" + re.escape(old))
        new_body, n = pattern.subn(new, new_body)
        counts[old] = n

    if all(c == 0 for c in counts.values()):
        return {"page_id": page_id, "title": title, "skipped": True, "counts": counts}

    payload = {
        "id": page_id,
        "type": "page",
        "title": title,
        "space": {"key": page["space"]["key"]},
        "version": {
            "number": version + 1,
            "message": "fix model IDs to us. prefix inference profiles (4세대 Anthropic 은 PROFILE 전용 — bare ID 호출 시 ValidationException)",
        },
        "body": {"storage": {"value": new_body, "representation": "storage"}},
    }
    request("PUT", f"/rest/api/content/{page_id}", body=payload)
    return {"page_id": page_id, "title": title, "skipped": False, "counts": counts,
             "new_version": version + 1}


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
        # dry-run: 어떤 페이지에 어떤 토큰이 몇 번 나오는지 보고만
        for pid in PAGE_IDS:
            page = request("GET", f"/rest/api/content/{pid}?expand=body.storage")
            body = page["body"]["storage"]["value"]
            import re
            for old, _new in REPLACEMENTS:
                pat = re.compile(r"(?<![a-zA-Z\.])" + re.escape(old))
                n = len(pat.findall(body))
                if n:
                    print(f"  {pid} {page['title'][:50]:50s}  {old} x {n}")
        return 0

    for pid in PAGE_IDS:
        try:
            result = fix_one(pid)
            print(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            print(f"FAIL {pid}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
