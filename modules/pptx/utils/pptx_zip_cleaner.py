#!/usr/bin/env python3
"""
PPTX Zip Cleaner — 참조되지 않은 슬라이드 XML을 PPTX zip에서 제거.

사용법:
    from scripts.utils.pptx_zip_cleaner import cleanup_pptx_orphans
    cleanup_pptx_orphans('/path/to/file.pptx')

문제 원인:
    python-pptx로 41장 템플릿 로드 후 sldIdLst에서 슬라이드 삭제해도,
    presentation.xml.rels에 원본 관계 유지 + OPC 패키지 레지스트리에 남아있음.
    save() 시 모든 파트가 zip에 기록되어 좀비 슬라이드 발생.
"""

import zipfile
import io
from lxml import etree

NS_P   = 'http://schemas.openxmlformats.org/presentationml/2006/main'
NS_R   = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS_REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
NS_CT  = 'http://schemas.openxmlformats.org/package/2006/content-types'


def cleanup_pptx_orphans(filepath: str, verbose: bool = True) -> None:
    """PPTX zip에서 sldIdLst에 참조되지 않은 슬라이드를 완전 제거.

    Args:
        filepath: .pptx 파일 경로
        verbose: 진행 상황 출력 여부
    """
    # ── 1. zip 읽기 (중복 항목 마지막 값 우선) ──────────────────────────
    all_data = {}
    with zipfile.ZipFile(filepath, 'r') as zf:
        for name in zf.namelist():
            all_data[name] = zf.read(name)  # 마지막 중복이 override

    # ── 2. presentation.xml → sldIdLst에서 참조 rId 수집 ────────────────
    prs_xml = etree.fromstring(all_data['ppt/presentation.xml'])
    sldIdLst = prs_xml.find(f'{{{NS_P}}}sldIdLst')
    referenced_rids = set()
    if sldIdLst is not None:
        for sldId in sldIdLst:
            rid = sldId.get(f'{{{NS_R}}}id')
            if rid:
                referenced_rids.add(rid)

    if verbose:
        print(f"  sldIdLst 참조 rId 수: {len(referenced_rids)}")

    # ── 3. presentation.xml.rels → 참조 슬라이드 경로 수집 + 필터링 ─────
    rels_xml = etree.fromstring(all_data['ppt/_rels/presentation.xml.rels'])
    referenced_slide_paths = set()  # e.g., 'ppt/slides/slide1.xml'
    removed_rids = set()

    new_rels_elem = etree.Element(f'{{{NS_REL}}}Relationships')
    for rel in rels_xml:
        rid = rel.get('Id', '')
        target = rel.get('Target', '')
        rel_type = rel.get('Type', '')
        is_slide = ('slide' in rel_type
                    and 'slideMaster' not in rel_type
                    and 'slideLayout' not in rel_type)

        if is_slide:
            if rid in referenced_rids:
                # 참조됨 — 유지
                referenced_slide_paths.add(f'ppt/{target}')
                new_rels_elem.append(rel)
            else:
                # 미참조 — 제거
                removed_rids.add(rid)
        else:
            # 비슬라이드 관계 — 항상 유지
            new_rels_elem.append(rel)

    # rels XML 갱신
    all_data['ppt/_rels/presentation.xml.rels'] = etree.tostring(
        new_rels_elem,
        xml_declaration=True,
        encoding='UTF-8',
        standalone=True
    )

    # ── 4. 미참조 슬라이드 XML + rels 파일 식별 및 제거 ─────────────────
    referenced_slide_rels = {
        f"ppt/slides/_rels/{p.split('/')[-1]}.rels"
        for p in referenced_slide_paths
    }

    to_remove = set()
    for name in list(all_data.keys()):
        if name.startswith('ppt/slides/') and '_rels' not in name:
            if name not in referenced_slide_paths:
                to_remove.add(name)
        elif 'ppt/slides/_rels/' in name:
            if name not in referenced_slide_rels:
                to_remove.add(name)

    for name in to_remove:
        del all_data[name]

    # ── 5. [Content_Types].xml → 미참조 슬라이드 Override 제거 ──────────
    ct_xml = etree.fromstring(all_data['[Content_Types].xml'])
    removed_ct = 0
    for override in list(ct_xml.findall(f'{{{NS_CT}}}Override')):
        part_name = override.get('PartName', '').lstrip('/')
        if 'ppt/slides/slide' in part_name and part_name not in referenced_slide_paths:
            ct_xml.remove(override)
            removed_ct += 1

    all_data['[Content_Types].xml'] = etree.tostring(
        ct_xml,
        xml_declaration=True,
        encoding='UTF-8',
        standalone=True
    )

    # ── 6. 정리된 zip 다시 쓰기 ─────────────────────────────────────────
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as new_zf:
        for name, data in sorted(all_data.items()):
            new_zf.writestr(name, data)

    with open(filepath, 'wb') as f:
        f.write(buf.getvalue())

    if verbose:
        print(f"  제거된 슬라이드 관계: {len(removed_rids)}개")
        print(f"  제거된 슬라이드 XML: {len(to_remove)}개")
        print(f"  제거된 ContentType Override: {removed_ct}개")
        print(f"  남은 슬라이드: {len(referenced_slide_paths)}개")


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("사용법: python pptx_zip_cleaner.py <file.pptx>")
        sys.exit(1)
    cleanup_pptx_orphans(sys.argv[1])
