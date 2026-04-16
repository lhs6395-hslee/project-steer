#!/usr/bin/env python3
"""
PPTX Integrity Checker & Auto-Fixer

PowerPoint "found a problem" 오류를 사전에 감지하고 자동 복구.

검사 항목:
  1. media 누락  — rels에서 참조되지만 zip에 파일 없음 → 템플릿에서 복원 시도
  2. media orphan — zip에 있지만 어떤 rels에서도 참조 안 됨 → 삭제
  3. Content_Types ghost — CT에 등록됐지만 zip에 파일 없음 → CT에서 제거
  4. 슬라이드 rels orphan image — slide*.xml.rels에 이미지 rel 있지만 slide XML에서 blip 없음 → 삭제

사용법:
    python pptx_integrity_check.py <file.pptx> [--template <template.pptx>] [--fix] [--verbose]

Python API:
    from modules.pptx.utils.pptx_integrity_check import check_and_fix_pptx
    issues = check_and_fix_pptx("file.pptx", template_path="template.pptx", fix=True)
"""

import zipfile
import io
import re
import sys
import argparse
from pathlib import Path


def _read_zip(path: str) -> dict[str, bytes]:
    """ZIP 파일을 dict로 읽기 (중복 항목은 마지막 값 우선)."""
    data = {}
    with zipfile.ZipFile(path, 'r') as zf:
        for name in zf.namelist():
            data[name] = zf.read(name)
    return data


def _write_zip(path: str, data: dict[str, bytes]) -> None:
    """dict를 ZIP 파일로 쓰기."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, content in sorted(data.items()):
            zf.writestr(name, content)
    with open(path, 'wb') as f:
        f.write(buf.getvalue())


def _get_rels_image_refs(data: dict[str, bytes]) -> dict[str, set[str]]:
    """모든 rels 파일에서 이미지 참조를 수집.

    Returns:
        {rels_path: {media_path, ...}}
    """
    result = {}
    for name, content in data.items():
        if not name.endswith(".rels"):
            continue
        refs = re.findall(r'Target="\.\.\/media\/([^"]+)"', content.decode())
        if refs:
            # rels 파일 위치에서 media 경로 계산
            # ppt/slides/_rels/slide1.xml.rels → ppt/media/image1.png
            rels_dir = name.rsplit("/", 1)[0]  # ppt/slides/_rels
            base_dir = rels_dir.replace("/_rels", "").replace("slides", "").replace("slideLayouts", "").replace("slideMasters", "")
            media_paths = set()
            for ref in refs:
                media_paths.add(f"ppt/media/{ref}")
            result[name] = media_paths
    return result


def _get_all_image_refs(data: dict[str, bytes]) -> set[str]:
    """모든 rels 파일의 이미지 참조를 합친 집합."""
    all_refs = set()
    for name, content in data.items():
        if not name.endswith(".rels"):
            continue
        refs = re.findall(r'Target="\.\.\/media\/([^"]+)"', content.decode())
        for ref in refs:
            all_refs.add(f"ppt/media/{ref}")
    return all_refs


def _get_slide_blip_rids(slide_xml: bytes) -> set[str]:
    """slide XML에서 실제로 사용되는 blip rId 목록 반환."""
    return set(re.findall(r'r:embed="(rId\d+)"', slide_xml.decode()))


def _get_slide_rels_image_rids(rels_xml: bytes) -> dict[str, str]:
    """slide rels XML에서 이미지 rId → media 파일명 맵 반환."""
    result = {}
    items = re.findall(
        r'Id="(rId\d+)"[^>]*Type="[^"]*relationships/image"[^>]*Target="\.\.\/media\/([^"]+)"',
        rels_xml.decode()
    )
    for rid, fname in items:
        result[rid] = fname
    return result


def check_and_fix_pptx(
    pptx_path: str,
    template_path: str | None = None,
    fix: bool = False,
    verbose: bool = True,
) -> list[dict]:
    """PPTX 무결성 검사 및 자동 복구.

    Args:
        pptx_path: 검사할 .pptx 파일 경로
        template_path: 이미지 복원에 사용할 원본 템플릿 경로
        fix: True면 자동 수정 후 덮어쓰기
        verbose: 진행 상황 출력 여부

    Returns:
        발견된 이슈 목록 (각 항목: {type, path, detail})
    """
    issues = []
    data = _read_zip(pptx_path)
    template_data = _read_zip(template_path) if template_path else {}

    media_in_zip = {n for n in data if n.startswith("ppt/media/")}
    all_refs = _get_all_image_refs(data)

    # ── 1. 누락 media (참조 있음 + 파일 없음) ──────────────────────────────
    missing_media = all_refs - media_in_zip
    for m in sorted(missing_media):
        issue = {"type": "missing_media", "path": m, "detail": "rels 참조 있지만 파일 없음"}
        issues.append(issue)
        if verbose:
            print(f"  ❌ [누락] {m}")

        if fix:
            if m in template_data:
                data[m] = template_data[m]
                issue["fixed"] = "템플릿에서 복원"
                if verbose:
                    print(f"     → ✅ 템플릿에서 복원 완료")
            else:
                issue["fixed"] = "복원 실패 (템플릿 없음)"
                if verbose:
                    print(f"     → ⚠️ 템플릿에 해당 파일 없음 — 수동 복원 필요")

    # ── 2. Orphan media (파일 있음 + 참조 없음) ────────────────────────────
    orphan_media = media_in_zip - all_refs
    for m in sorted(orphan_media):
        issue = {"type": "orphan_media", "path": m, "detail": "파일 있지만 어떤 rels에서도 참조 안 됨"}
        issues.append(issue)
        if verbose:
            print(f"  ⚠️ [orphan] {m}")

        if fix:
            del data[m]
            issue["fixed"] = "파일 삭제"
            if verbose:
                print(f"     → ✅ 삭제 완료")

    # ── 3. Content_Types ghost entries ─────────────────────────────────────
    ct_content = data.get("[Content_Types].xml", b"").decode()
    ct_part_names = re.findall(r'PartName="(/[^"]+)"', ct_content)
    for part in ct_part_names:
        zip_key = part.lstrip("/")
        if zip_key.startswith("ppt/media/") and zip_key not in data:
            issue = {"type": "ct_ghost", "path": part, "detail": "CT 등록 있지만 파일 없음"}
            issues.append(issue)
            if verbose:
                print(f"  ❌ [CT ghost] {part}")

            if fix:
                # CT에서 해당 Override 제거
                ct_content = re.sub(
                    rf'<Override[^>]*PartName="{re.escape(part)}"[^/]*/>', "", ct_content
                )
                issue["fixed"] = "CT에서 제거"
                if verbose:
                    print(f"     → ✅ Content_Types에서 제거")

    if fix and "[Content_Types].xml" in data:
        data["[Content_Types].xml"] = ct_content.encode()

    # ── 4. Slide rels 내 orphan image rel (blip 참조 없는 rId) ─────────────
    for name in sorted(data.keys()):
        if not (name.startswith("ppt/slides/_rels/") and name.endswith(".xml.rels")):
            continue
        slide_name = name.replace("/_rels", "").replace(".rels", "")
        if slide_name not in data:
            continue

        blip_rids = _get_slide_blip_rids(data[slide_name])
        img_rels = _get_slide_rels_image_rids(data[name])

        for rid, fname in img_rels.items():
            if rid not in blip_rids:
                issue = {
                    "type": "orphan_slide_rel",
                    "path": name,
                    "detail": f"rId={rid} → {fname} — slide XML blip 참조 없음"
                }
                issues.append(issue)
                if verbose:
                    print(f"  ⚠️ [orphan rel] {name}: {rid} → {fname}")

                if fix:
                    # rels XML에서 해당 Relationship 제거
                    rels_str = data[name].decode()
                    rels_str = re.sub(
                        rf'<Relationship[^>]*Id="{re.escape(rid)}"[^/]*/>', "", rels_str
                    )
                    data[name] = rels_str.encode()
                    issue["fixed"] = "rels에서 제거"
                    if verbose:
                        print(f"     → ✅ rels에서 제거")

    # ── 결과 저장 ───────────────────────────────────────────────────────────
    if fix and issues:
        _write_zip(pptx_path, data)
        if verbose:
            print(f"\n✅ 수정 완료 → {pptx_path}")
    elif not issues:
        if verbose:
            print("✅ 이상 없음")
    else:
        if verbose:
            print(f"\n⚠️ {len(issues)}개 이슈 발견 (--fix 옵션으로 자동 수정 가능)")

    return issues


def main():
    parser = argparse.ArgumentParser(description="PPTX 무결성 검사 및 자동 수정")
    parser.add_argument("pptx", help=".pptx 파일 경로")
    parser.add_argument("--template", help="이미지 복원용 원본 템플릿 경로")
    parser.add_argument("--fix", action="store_true", help="자동 수정 적용")
    parser.add_argument("--quiet", action="store_true", help="출력 최소화")
    args = parser.parse_args()

    if not Path(args.pptx).exists():
        print(f"오류: 파일 없음 — {args.pptx}")
        sys.exit(1)

    print(f"검사 중: {args.pptx}")
    issues = check_and_fix_pptx(
        pptx_path=args.pptx,
        template_path=args.template,
        fix=args.fix,
        verbose=not args.quiet,
    )

    if issues:
        sys.exit(1)  # CI에서 오류 감지 가능


if __name__ == "__main__":
    main()
