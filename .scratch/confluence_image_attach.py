#!/usr/bin/env python3
"""Confluence Cloud REST API로 워크샵 이미지를 페이지에 첨부하고 본문 placeholder를 치환.

Idempotent: 같은 파일명으로 이미 attachment가 있으면 업로드 스킵, 본문에 이미지 매크로가
있으면 추가하지 않음. 안전하게 N번 재실행 가능.

필수 환경변수
  CONFLUENCE_BASE_URL   예: https://toule.atlassian.net/wiki
  CONFLUENCE_EMAIL      Atlassian 계정 이메일
  CONFLUENCE_API_TOKEN  https://id.atlassian.com/manage-profile/security/api-tokens
                        에서 발급한 토큰
  IMAGES_ROOT (선택)    이미지 루트. 기본: 아래 IMAGES_ROOT_DEFAULT
"""
from __future__ import annotations

import json
import os
import re
import sys
from base64 import b64encode
from pathlib import Path
from typing import Iterable

import urllib.request
import urllib.error

IMAGES_ROOT_DEFAULT = (
    "/Users/toule/Documents/Works/2026/교육용자료/agenticai/"
    "workshop-extract/workshop-images"
)

# ── 페이지별 이미지 매핑 ─────────────────────────────────────────────────
# manifest.json 의 슬러그 → 페이지 ID. 각 항목은 (그 페이지 본문에 박을) 이미지
# 파일 경로 리스트와 캡션을 가진다. prerequisites/* 는 Workshop Studio UI 전용
# 이라 셀프호스팅 위키에서는 제외.
#
# 페이지 ID 는 이전 단계에서 발급받은 것:
#   Lab-1   909901826
#   Lab-2   909934594
#   Lab-3   909869090
#   Lab-4   909869118
#   Lab-5   910295051
#   Lab-6   910360578
PAGE_IMAGES: list[dict] = [
    # Lab-1: FAQ Agent (Bedrock Agent vs Strands)
    {
        "page_id": "909901826",
        "section_anchor": "## 3. Lab-1a — Bedrock Agent (관리형)",
        "title": "Lab-1a 콘솔 스크린샷",
        "items": [
            ("lab-1a/00-FAQBRAgent.png", "Bedrock FAQ Agent 아키텍처"),
            ("lab-1a/create-agent/00-CreateAgent.png", "Bedrock Agent 생성 페이지"),
            ("lab-1a/create-agent/01-SelectAgentName.png", "에이전트 이름 입력"),
            ("lab-1a/create-agent/02-AgentBuilder.png", "모델 선택 후 Save"),
            ("lab-1a/create-agent/03-AddKB.png", "에이전트에 Knowledge Base 추가"),
            ("lab-1a/create-agent/04-AgentPrepare.png", "Agent Prepare"),
            ("lab-1a/create-agent/05-AgentTest.png", "Agent Test"),
            ("lab-1b/00-FAQ-agent-v2.png", "Strands FAQ Agent 아키텍처 (Lab-1b)"),
        ],
    },
    # Lab-2: 제품 검색 — MCP Gateway + Guardrails
    {
        "page_id": "909934594",
        "section_anchor": "## ",
        "title": "Lab-2 아키텍처 + 콘솔 캡처",
        "items": [
            (
                "lab-2/product-search-agent-with-mcp-tools/"
                "00-product-search-architecture.png",
                "제품 검색 에이전트 아키텍처",
            ),
            (
                "lab-2/product-search-agent-with-mcp-tools/"
                "02-Agentcore-homepage.png",
                "AgentCore 홈",
            ),
            (
                "lab-2/product-search-agent-with-mcp-tools/"
                "03-Agentcore-creategateway.png",
                "AgentCore Gateway 생성",
            ),
            (
                "lab-2/product-search-agent-with-mcp-tools/"
                "04-Agentcore-discoveryurl.png",
                "Discovery URL 입력",
            ),
            (
                "lab-2/product-search-agent-with-mcp-tools/"
                "05-Agentcore-clientid.png",
                "Cognito 클라이언트 ID 입력",
            ),
            (
                "lab-2/product-search-agent-with-mcp-tools/"
                "06-Agentcore-target.png",
                "타겟으로 Lambda 선택",
            ),
            (
                "lab-2/product-search-agent-with-mcp-tools/"
                "07-gatewayurl.png",
                "게이트웨이 리소스 URL 복사",
            ),
            (
                "lab-2/product-search-agent-with-guardrails/"
                "00-product-search-architecture-with-guardrails.png",
                "Guardrails 적용 후 아키텍처",
            ),
        ],
    },
    # Lab-3: 재고 에이전트
    {
        "page_id": "909869090",
        "section_anchor": "## ",
        "title": "Lab-3 아키텍처",
        "items": [
            ("lab-3/00-Inventory-agents.png", "재고 에이전트 아키텍처"),
        ],
    },
    # Lab-4: 오케스트레이터
    {
        "page_id": "909869118",
        "section_anchor": "## ",
        "title": "Lab-4 아키텍처",
        "items": [
            ("lab-4/00-orchestrator.png", "Orchestrator Agent"),
            ("lab-4/01-overall-architecture-v4.png", "전체 아키텍처"),
        ],
    },
    # Lab-5: Runtime 배포 (3가지 패턴)
    {
        "page_id": "910295051",
        "section_anchor": "## ",
        "title": "Lab-5 3가지 배포 패턴",
        "items": [
            (
                "lab-5/deploy-agents-as-tools/00-arch-agents-deployed-as-tools.png",
                "Agents-as-Tools 패턴",
            ),
            (
                "lab-5/deploy-autonomous-agents/00-arch-autonomous-agents.png",
                "Autonomous Agents (boto3) 패턴",
            ),
            (
                "lab-5/deploy-autonomous-agents-with-a2a/"
                "00-arch-autonomous-agents-with-a2a.png",
                "A2A Autonomous Agents 패턴",
            ),
        ],
    },
    # Lab-6: Observability + Evaluations
    {
        "page_id": "910360578",
        "section_anchor": "## 3. CloudWatch 콘솔 사용",
        "title": "Lab-6 CloudWatch GenAI Observability + AgentCore Evaluations",
        "items": [
            (
                "lab-6/agentcoreobservability/00-cw-span-injection-enabled.png",
                "CloudWatch Transaction Search 활성화",
            ),
            (
                "lab-6/agentcoreobservability/01-cw-genai-observability-1.png",
                "Generative AI Observability 개요",
            ),
            (
                "lab-6/agentcoreobservability/02-cw-genai-observability-2.png",
                "런타임 메트릭 포함 에이전트 개요",
            ),
            (
                "lab-6/agentcoreobservability/03-cw-genai-observability-3.png",
                "Sessions / Traces / Tokens / Errors / Throttles",
            ),
            (
                "lab-6/agentcoreobservability/04-cw-genai-observability-4.png",
                "세션 상세 + 트레이스 목록",
            ),
            (
                "lab-6/agentcoreobservability/05-cw-genai-observability-5.png",
                "A2A 오케스트레이터 트레이스 + 스팬 트리",
            ),
            (
                "lab-6/agentcoreobservability/06-cw-genai-observability-6.png",
                "Trajectory 그래프 + 이벤트",
            ),
            (
                "lab-6/agentcoreobservability/07-cw-genai-observability-7.png",
                "gen_ai.choice 이벤트 + 토큰 카운트",
            ),
            ("lab-6/agentcoreevaluations/00-eval-1.png", "AgentCore Evaluations 페이지"),
            ("lab-6/agentcoreevaluations/01-eval-2.png", "평가 데이터 소스 구성"),
            ("lab-6/agentcoreevaluations/02-eval-3.png", "평가기 선택"),
            ("lab-6/agentcoreevaluations/03-eval-4.png", "평가 검토 및 생성"),
            (
                "lab-6/agentcoreevaluations/04-eval-result-view.png",
                "평가 구성 세부 정보",
            ),
            ("lab-6/agentcoreevaluations/05-eval-results-1.png", "CloudWatch 평가 결과"),
            ("lab-6/agentcoreevaluations/06-eval-results-2.png", "평가 점수 세부 정보"),
            (
                "lab-6/agentcoreevaluations/07-eval-results-3.png",
                "세션 수준 평가 세부 정보",
            ),
            ("lab-6/agentcoreevaluations/08-eval-results-4.png", "평가 로그"),
            ("lab-6/agentcoreevaluations/09-eval-results-5.png", "평가 메트릭"),
        ],
    },
]


# ── HTTP helpers ────────────────────────────────────────────────────────
class HTTPError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}: {body[:500]}")
        self.status = status
        self.body = body


def _auth_header(email: str, token: str) -> str:
    raw = f"{email}:{token}".encode()
    return "Basic " + b64encode(raw).decode()


def _request(
    method: str,
    url: str,
    *,
    auth: str,
    headers: dict | None = None,
    data: bytes | None = None,
) -> dict:
    h = {"Authorization": auth, "Accept": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8") or "{}"
            return json.loads(body) if body.strip().startswith(("{", "[")) else {"_raw": body}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise HTTPError(e.code, body) from None


# ── Confluence v1 REST (attachment 작업은 v1만 지원) ─────────────────────
def get_attachments(base_url: str, page_id: str, auth: str) -> list[dict]:
    """페이지의 모든 attachment (paged). filename → metadata."""
    out, start = [], 0
    while True:
        u = (
            f"{base_url}/rest/api/content/{page_id}/child/attachment"
            f"?limit=200&start={start}"
        )
        data = _request("GET", u, auth=auth)
        out.extend(data.get("results", []))
        if data.get("size", 0) < 200:
            break
        start += 200
    return out


def upload_attachment(
    base_url: str, page_id: str, file_path: Path, auth: str
) -> dict:
    """multipart/form-data 로 attachment 업로드. 같은 이름이면 새 버전을 만든다."""
    boundary = "----confluence-img-attach-" + os.urandom(8).hex()
    filename = file_path.name
    content_type = "image/png" if filename.lower().endswith(".png") else "image/jpeg"

    body = bytearray()
    body += f"--{boundary}\r\n".encode()
    body += (
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode()
    body += file_path.read_bytes()
    body += f"\r\n--{boundary}--\r\n".encode()

    url = f"{base_url}/rest/api/content/{page_id}/child/attachment"
    data = _request(
        "POST",
        url,
        auth=auth,
        headers={
            "X-Atlassian-Token": "no-check",  # XSRF 우회용 필수 헤더
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        data=bytes(body),
    )
    return data


def get_page_storage(base_url: str, page_id: str, auth: str) -> tuple[dict, str]:
    """페이지 metadata + storage 본문 반환."""
    u = f"{base_url}/rest/api/content/{page_id}?expand=body.storage,version,space"
    data = _request("GET", u, auth=auth)
    return data, data["body"]["storage"]["value"]


def update_page_storage(
    base_url: str, page_id: str, page: dict, new_storage: str, auth: str
) -> dict:
    """동일 page version+1 로 PUT."""
    payload = {
        "id": page_id,
        "type": "page",
        "title": page["title"],
        "space": {"key": page["space"]["key"]},
        "version": {
            "number": page["version"]["number"] + 1,
            "message": "워크샵 이미지 attachment 일괄 첨부 (idempotent)",
        },
        "body": {
            "storage": {"value": new_storage, "representation": "storage"},
        },
    }
    return _request(
        "PUT",
        f"{base_url}/rest/api/content/{page_id}",
        auth=auth,
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload).encode("utf-8"),
    )


# ── Body 변형 ───────────────────────────────────────────────────────────
def build_image_block(items: list[tuple[str, str]]) -> str:
    """파일경로/캡션 쌍을 받아 ac:image 블록 문자열 반환.

    캡션은 alt + 본문 아래 작은 글씨로.
    """
    parts = ['<h3>워크샵 스크린샷</h3>']
    for path, caption in items:
        filename = Path(path).name
        # storage format: ri:attachment 만으로 같은 페이지의 attachment 참조
        parts.append(
            f'<p><ac:image ac:alt="{caption}" ac:width="800">'
            f'<ri:attachment ri:filename="{filename}" />'
            f'</ac:image></p>'
            f'<p><em>{caption}</em></p>'
        )
    return "\n".join(parts)


SECTION_TAG_OPEN = '<!-- WORKSHOP_IMAGES_BEGIN -->'
SECTION_TAG_CLOSE = '<!-- WORKSHOP_IMAGES_END -->'


def upsert_image_section(storage: str, image_block: str) -> str:
    """본문 끝쪽에 마커로 둘러싼 이미지 섹션을 멱등 삽입/갱신.

    이미 마커가 있으면 그 안만 새 block 으로 교체. 없으면 본문 끝에 append.
    """
    section = f"{SECTION_TAG_OPEN}\n{image_block}\n{SECTION_TAG_CLOSE}"
    pat = re.compile(
        re.escape(SECTION_TAG_OPEN) + r".*?" + re.escape(SECTION_TAG_CLOSE),
        re.DOTALL,
    )
    if pat.search(storage):
        return pat.sub(section, storage)
    return storage.rstrip() + "\n" + section + "\n"


# ── Main flow ───────────────────────────────────────────────────────────
def process_page(
    base_url: str,
    auth: str,
    images_root: Path,
    page_def: dict,
    *,
    dry_run: bool = False,
) -> None:
    page_id = page_def["page_id"]
    items = page_def["items"]
    print(f"\n=== page {page_id} ({page_def['title']}) ===")

    # 1) 파일 존재 확인 + 절대 경로로 변환
    resolved: list[tuple[Path, str]] = []
    for rel, caption in items:
        p = images_root / rel
        if not p.is_file():
            print(f"  skip (file missing): {rel}")
            continue
        resolved.append((p, caption))
    if not resolved:
        print("  (no images for this page)")
        return

    # 2) 기존 attachment 인덱스 (filename set)
    existing = (
        {a["title"] for a in get_attachments(base_url, page_id, auth)}
        if not dry_run
        else set()
    )
    # 3) 업로드 누락 분만
    for path, _caption in resolved:
        if path.name in existing:
            print(f"  attach exists, skip: {path.name}")
            continue
        if dry_run:
            print(f"  [dry] would upload: {path.name} ({path.stat().st_size} B)")
            continue
        try:
            upload_attachment(base_url, page_id, path, auth)
            print(f"  uploaded: {path.name}")
        except HTTPError as e:
            print(f"  ! upload failed: {path.name} -> {e}")

    # 4) 본문에 image section 멱등 삽입/갱신
    image_block = build_image_block(
        [(p.name, c) for p, c in resolved]  # filename 만 본문에 박기
    )
    if dry_run:
        print("  [dry] body would be patched with image section")
        return

    page, storage = get_page_storage(base_url, page_id, auth)
    new_storage = upsert_image_section(storage, image_block)
    if new_storage == storage:
        print("  body already up-to-date, skip update")
        return
    update_page_storage(base_url, page_id, page, new_storage, auth)
    print("  body updated")


def main(argv: list[str]) -> int:
    base_url = os.environ.get(
        "CONFLUENCE_BASE_URL", "https://toule.atlassian.net/wiki"
    ).rstrip("/")
    email = os.environ.get("CONFLUENCE_EMAIL")
    token = os.environ.get("CONFLUENCE_API_TOKEN")
    images_root = Path(os.environ.get("IMAGES_ROOT", IMAGES_ROOT_DEFAULT))

    dry_run = "--dry-run" in argv

    if not dry_run and not (email and token):
        print(
            "ERROR: CONFLUENCE_EMAIL / CONFLUENCE_API_TOKEN 필요.\n"
            "  발급: https://id.atlassian.com/manage-profile/security/api-tokens\n"
            "  사용:\n"
            "    export CONFLUENCE_EMAIL='you@example.com'\n"
            "    export CONFLUENCE_API_TOKEN='...'\n"
            "    python confluence_image_attach.py\n"
            "(또는 토큰 없이 검증만: python confluence_image_attach.py --dry-run)",
            file=sys.stderr,
        )
        return 2

    auth = _auth_header(email or "x", token or "x")

    if not images_root.is_dir():
        print(f"ERROR: IMAGES_ROOT not a directory: {images_root}", file=sys.stderr)
        return 2

    print(
        f"base_url    = {base_url}\n"
        f"images_root = {images_root}\n"
        f"dry_run     = {dry_run}\n"
        f"pages       = {len(PAGE_IMAGES)}"
    )

    for pdef in PAGE_IMAGES:
        try:
            process_page(base_url, auth, images_root, pdef, dry_run=dry_run)
        except HTTPError as e:
            print(f"  ! page {pdef['page_id']} failed: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"  ! page {pdef['page_id']} failed: {e}")

    print("\ndone.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
