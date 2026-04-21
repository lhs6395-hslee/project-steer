"""
fix_toc.py — TOC 재구성 + 중제목 라벨 업데이트 유틸리티
Usage:
  python fix_toc.py <file.pptx> --sections "제목1" "제목2" ... [--labels <slide_num>:"라벨":"설명" ...]
  python fix_toc.py <file.pptx> --from-config <config.json>

기능:
  1. TOC 슬라이드(slide2) 번호/제목 재구성
  2. 섹션이 6개 이상이면 두 번째 목차 슬라이드를 deepcopy로 추가 (5개씩 페이징)
  3. 본문 슬라이드의 중제목 라벨(TextBox 17/18) 업데이트
"""

import argparse
import copy
import json
import re
import sys
import uuid
import zipfile
from pathlib import Path

import lxml.etree as ET

# ── Namespaces ────────────────────────────────────────────────────────────────
NSP = 'http://schemas.openxmlformats.org/presentationml/2006/main'
NSA = 'http://schemas.openxmlformats.org/drawingml/2006/main'
NSR = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NSR2 = 'http://schemas.openxmlformats.org/package/2006/relationships'
P14 = 'http://schemas.microsoft.com/office/powerpoint/2010/main'

SLIDE_REL_TYPE = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide'
ITEMS_PER_PAGE = 5

# TOC 제목 최대 너비 — TextBox 49 cx=3,927,168 EMU, 24pt 기준
# 한글 1.0em, ASCII 0.6em, 공백 0.28em (check_textbox_overflow.py 동일 기준)
TOC_BOX_W_EMU = 3_927_168
TOC_FONT_PT   = 24.0
PT_TO_EMU_TOC = 12_700

def _toc_title_width_em(title: str) -> float:
    total = 0.0
    for ch in title:
        cp = ord(ch)
        if (0xAC00 <= cp <= 0xD7A3 or 0x1100 <= cp <= 0x11FF or
                0x4E00 <= cp <= 0x9FFF or 0xFF00 <= cp <= 0xFFEF):
            total += 1.0
        elif ch == ' ':
            total += 0.28
        elif 0x21 <= cp <= 0x7E:
            total += 0.60
        else:
            total += 0.85
    return total

def validate_toc_titles(sections: list[str]) -> list[str]:
    """
    각 섹션 제목이 TOC TextBox에 한 줄로 들어가는지 검증.
    최대 em 너비: TOC_BOX_W_EMU / (TOC_FONT_PT * PT_TO_EMU_TOC)
    초과 시 WARNING 메시지 반환.
    """
    max_em = TOC_BOX_W_EMU / (TOC_FONT_PT * PT_TO_EMU_TOC)
    warnings = []
    for i, title in enumerate(sections, 1):
        em = _toc_title_width_em(title)
        if em > max_em:
            warnings.append(
                f'WARNING: 섹션 {i} 제목이 너무 김 ({em:.1f}em > {max_em:.1f}em): "{title}"'
                f' → 줄바꿈 발생, 번호 컬럼과 어긋남'
            )
    return warnings

# ── TOC paragraph template builders ──────────────────────────────────────────

def _clone_para_with_text(template_para: ET._Element, new_text: str) -> ET._Element:
    """Clone a paragraph element and replace its a:t text."""
    p = copy.deepcopy(template_para)
    for t_el in p.iter(f'{{{NSA}}}t'):
        t_el.text = new_text
        break   # only first a:t
    return p


def _update_toc_textboxes(slide_root: ET._Element, numbers: list[str], titles: list[str]):
    """
    Update TextBox 48 (number column) and TextBox 49 (title column) in a TOC slide.
    Replaces existing paragraphs with exactly len(numbers) paragraphs.
    """
    assert len(numbers) == len(titles), "numbers and titles must be same length"

    for sp in slide_root.iter(f'{{{NSP}}}sp'):
        nvpr = sp.find(f'.//{{{NSP}}}nvSpPr/{{{NSP}}}cNvPr')
        if nvpr is None:
            continue
        name = nvpr.get('name', '')
        if name not in ('TextBox 48', 'TextBox 49'):
            continue

        txBody = sp.find(f'{{{NSP}}}txBody')   # p:txBody, not a:txBody
        if txBody is None:
            continue

        existing_paras = txBody.findall(f'{{{NSA}}}p')
        if not existing_paras:
            continue

        # Use the first paragraph as the template (preserves formatting)
        template_para = copy.deepcopy(existing_paras[0])

        # Remove all existing paragraphs
        for p in existing_paras:
            txBody.remove(p)

        # Insert new paragraphs
        items = numbers if name == 'TextBox 48' else titles
        for item in items:
            txBody.append(_clone_para_with_text(template_para, item))


# ── Presentation XML helpers ──────────────────────────────────────────────────

def _get_max_sld_id(prs_root: ET._Element) -> int:
    ids = [int(s.get('id', 0)) for s in prs_root.iter(f'{{{NSP}}}sldId')]
    return max(ids) if ids else 255


def _get_slide_rels(prs_root: ET._Element) -> list[tuple[str, str]]:
    """Return list of (rId, slide_path) in slide order from sldIdLst."""
    rid_to_path = {}
    rels_root = prs_root  # caller will provide rels separately
    return rid_to_path


def _find_toc_slide_position(prs_root: ET._Element) -> int:
    """Return 0-based index of the first TOC slide in sldIdLst (usually index 1)."""
    sld_id_lst = prs_root.find(f'{{{NSP}}}sldIdLst')
    if sld_id_lst is None:
        return 1
    children = list(sld_id_lst)
    # TOC is usually index 1 (after cover at index 0)
    return 1


def _insert_sld_id_after(prs_root: ET._Element, after_idx: int, new_id: int, new_rid: str):
    """Insert a new sldId element after position after_idx in sldIdLst."""
    sld_id_lst = prs_root.find(f'{{{NSP}}}sldIdLst')
    children = list(sld_id_lst)
    new_el = ET.SubElement(ET.Element('dummy'), f'{{{NSP}}}sldId')
    new_el = ET.fromstring(
        f'<p:sldId xmlns:p="{NSP}" xmlns:r="{NSR}" id="{new_id}" r:id="{new_rid}"/>'
    )
    if after_idx + 1 < len(children):
        children[after_idx + 1].addprevious(new_el)
    else:
        sld_id_lst.append(new_el)


def _add_prs_rel(rels_root: ET._Element, rid: str, slide_path: str):
    """Add a slide relationship to presentation.xml.rels.
    slide_path should be 'slides/slideN.xml' (relative to ppt/).
    """
    ET.SubElement(rels_root, f'{{{NSR2}}}Relationship', {
        'Id': rid,
        'Type': SLIDE_REL_TYPE,
        'Target': slide_path,   # e.g. 'slides/slide11.xml'
    })


def _update_section_lst(prs_root: ET._Element, toc_slide_ids: list[int]):
    """
    Update 목차 section in sectionLst to include all TOC slide IDs.
    Finds the section named '목차' and replaces its sldIdLst.
    """
    ext_lst = prs_root.find(f'.//{{{NSP}}}extLst')
    if ext_lst is None:
        return
    for ext in ext_lst.iter(f'{{{NSP}}}ext'):
        for section_lst in ext.iter(f'{{{P14}}}sectionLst'):
            for section in section_lst.findall(f'{{{P14}}}section'):
                if section.get('name') == '목차':
                    # Clear existing sldIdLst and rebuild
                    sldLst = section.find(f'{{{P14}}}sldIdLst')
                    if sldLst is None:
                        sldLst = ET.SubElement(section, f'{{{P14}}}sldIdLst')
                    else:
                        for child in list(sldLst):
                            sldLst.remove(child)
                    for sid in toc_slide_ids:
                        ET.SubElement(sldLst, f'{{{P14}}}sldId', {'id': str(sid)})
                    return


# ── Slide XML builder for page 2+ ─────────────────────────────────────────────

def _new_slide_from_template(template_slide_xml: bytes, new_numbers: list[str],
                              new_titles: list[str]) -> bytes:
    """Deepcopy a TOC slide XML, update with new_numbers/new_titles, return bytes."""
    root = ET.fromstring(template_slide_xml)
    _update_toc_textboxes(root, new_numbers, new_titles)
    return ET.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)


def _copy_slide_rels(all_files: dict, src_rel_path: str, dst_rel_path: str):
    """Copy slide relationship file (for layout, master refs)."""
    if src_rel_path in all_files:
        all_files[dst_rel_path] = all_files[src_rel_path]


# ── Subtitle label updater ─────────────────────────────────────────────────────

def _update_subtitle_label(slide_xml: bytes, label: str, desc: str | None) -> bytes:
    """
    Replace TextBox 17 (label) and TextBox 18 (description) text in a body slide.
    Collapses all runs in the first text paragraph into a single a:r with new text,
    preserving the rPr formatting of the original first run.
    If desc is None, TextBox 18 is left unchanged.
    """
    root = ET.fromstring(slide_xml)
    for sp in root.iter(f'{{{NSP}}}sp'):
        nvpr = sp.find(f'.//{{{NSP}}}nvSpPr/{{{NSP}}}cNvPr')
        if nvpr is None:
            continue
        name = nvpr.get('name', '')
        if name not in ('TextBox 17', 'TextBox 18'):
            continue

        new_text = label if name == 'TextBox 17' else desc
        if new_text is None:
            continue  # skip TextBox 18 when desc not provided
        txBody = sp.find(f'{{{NSP}}}txBody')
        if txBody is None:
            continue

        # Get the FIRST paragraph that has text
        paras = txBody.findall(f'{{{NSA}}}p')
        target_para = None
        for p in paras:
            if any(t.text and t.text.strip() for t in p.iter(f'{{{NSA}}}t')):
                target_para = p
                break
        if target_para is None and paras:
            target_para = paras[0]
        if target_para is None:
            continue

        # Grab formatting from the first existing run (preserve rPr)
        first_rpr = target_para.find(f'.//{{{NSA}}}r/{{{NSA}}}rPr')
        rpr_clone = copy.deepcopy(first_rpr) if first_rpr is not None else None

        # Remove ALL existing runs (a:r) from this paragraph
        for r in list(target_para.findall(f'{{{NSA}}}r')):
            target_para.remove(r)

        # Build a single new run with the new text
        new_r = ET.SubElement(target_para, f'{{{NSA}}}r')
        if rpr_clone is not None:
            new_r.insert(0, rpr_clone)
        new_t = ET.SubElement(new_r, f'{{{NSA}}}t')
        new_t.text = new_text

        # Remove all OTHER paragraphs (keep only first)
        for p in paras[1:]:
            txBody.remove(p)

    return ET.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)


# ── Main rebuild function ──────────────────────────────────────────────────────

def rebuild_toc(pptx_path: str | Path, sections: list[str],
                slide_labels: dict[int, tuple[str, str]] | None = None) -> list[str]:
    """
    Rebuild TOC and optionally update subtitle labels.

    Args:
      pptx_path: path to pptx file (modified in-place)
      sections:  list of section title strings (1-based order)
      slide_labels: optional dict {slide_num_1based: (label_text, description)}
                    e.g. {3: ("AS-IS / TO-BE", "현재 한계와 목표 상태 비교")}
                    If None, auto-generates from sections with "N. 섹션명" format.
                    Label text should NOT include the number prefix — it is auto-prepended.

    Returns list of fix messages.
    """
    pptx_path = Path(pptx_path)
    fixes = []

    # ── Validate title lengths before writing ────────────────────────────────
    warnings = validate_toc_titles(sections)
    for w in warnings:
        print(w, file=sys.stderr)
        fixes.append(w)

    # Read all files
    with zipfile.ZipFile(pptx_path) as z:
        all_files = {n: z.read(n) for n in z.namelist()}

    # ── Parse presentation.xml ────────────────────────────────────────────────
    prs_xml = all_files['ppt/presentation.xml']
    prs_root = ET.fromstring(prs_xml)

    prs_rels_xml = all_files['ppt/_rels/presentation.xml.rels']
    prs_rels_root = ET.fromstring(prs_rels_xml)

    # Build rId → slide path map
    rid_to_slide = {}
    for rel in prs_rels_root.findall(f'{{{NSR2}}}Relationship'):
        if rel.get('Type') == SLIDE_REL_TYPE:
            target = rel.get('Target', '').lstrip('./')
            rid_to_slide[rel.get('Id')] = target

    # Build ordered slide list from sldIdLst
    sld_id_lst = prs_root.find(f'{{{NSP}}}sldIdLst')
    ordered_slides: list[tuple[int, str, str]] = []  # (sld_id, rId, slide_path)
    for sld_el in sld_id_lst:
        sid = int(sld_el.get('id', 0))
        rid = sld_el.get(f'{{{NSR}}}id', '')
        path = rid_to_slide.get(rid, '')
        ordered_slides.append((sid, rid, path))

    # TOC slide is index 1 (0=cover)
    toc_idx = 1
    toc_sld_id, toc_rid, toc_path = ordered_slides[toc_idx]
    toc_slide_xml = all_files[f'ppt/{toc_path}']

    # ── Page 1: update existing TOC slide (items 1–5) ────────────────────────
    page1_sections = sections[:ITEMS_PER_PAGE]
    page1_numbers = [str(i + 1) for i in range(len(page1_sections))]

    toc_root = ET.fromstring(toc_slide_xml)
    _update_toc_textboxes(toc_root, page1_numbers, page1_sections)
    all_files[f'ppt/{toc_path}'] = ET.tostring(
        toc_root, xml_declaration=True, encoding='UTF-8', standalone=True)
    fixes.append(f'TOC page 1: updated {len(page1_sections)} sections')

    # ── Page 2+: insert additional TOC slides if needed ─────────────────────
    toc_slide_ids_for_section = [toc_sld_id]

    if len(sections) > ITEMS_PER_PAGE:
        # Existing max sldId and rId number
        max_sld_id = _get_max_sld_id(prs_root)
        existing_rids = {rel.get('Id', '') for rel in prs_rels_root.findall(f'{{{NSR2}}}Relationship')}
        max_rid_num = max(
            (int(re.sub(r'\D', '', r)) for r in existing_rids if re.search(r'\d', r)),
            default=20
        )

        # For each additional page
        remaining = sections[ITEMS_PER_PAGE:]
        page_num = 2
        insert_after_idx = toc_idx  # insert right after current TOC page

        while remaining:
            chunk = remaining[:ITEMS_PER_PAGE]
            remaining = remaining[ITEMS_PER_PAGE:]
            chunk_numbers = [str(ITEMS_PER_PAGE * (page_num - 1) + i + 1) for i in range(len(chunk))]

            # New slide XML
            new_slide_xml = _new_slide_from_template(toc_slide_xml, chunk_numbers, chunk)

            # New IDs
            max_sld_id += 1
            new_sld_id = max_sld_id
            max_rid_num += 1
            new_rid = f'rId{max_rid_num}'

            # Determine slide filename (next available slide number)
            existing_nums = set()
            for _, _, sp in ordered_slides:
                m = re.search(r'slides/slide(\d+)\.xml', sp)
                if m:
                    existing_nums.add(int(m.group(1)))
            new_slide_num = max(existing_nums) + 1 if existing_nums else 100
            new_slide_fname = f'slides/slide{new_slide_num}.xml'
            new_slide_full = f'ppt/{new_slide_fname}'

            # Store new slide
            all_files[new_slide_full] = new_slide_xml

            # Copy rels from the original TOC slide
            toc_rel_path = f'ppt/slides/_rels/{toc_path.split("/")[-1]}.rels'
            new_rel_path = f'ppt/slides/_rels/slide{new_slide_num}.xml.rels'
            _copy_slide_rels(all_files, toc_rel_path, new_rel_path)

            # Add to [Content_Types].xml
            ct_xml = all_files.get('[Content_Types].xml', b'')
            ct_root = ET.fromstring(ct_xml)
            part_name = f'/ppt/{new_slide_fname}'
            if not any(o.get('PartName') == part_name for o in ct_root):
                ET.SubElement(ct_root, 'Override', {
                    'PartName': part_name,
                    'ContentType': 'application/vnd.openxmlformats-officedocument.presentationml.slide+xml',
                })
            all_files['[Content_Types].xml'] = ET.tostring(
                ct_root, xml_declaration=True, encoding='UTF-8', standalone=True)

            # Add relationship to presentation.xml.rels
            _add_prs_rel(prs_rels_root, new_rid, new_slide_fname)

            # Insert sldId into sldIdLst after insert_after_idx
            _insert_sld_id_after(prs_root, insert_after_idx, new_sld_id, new_rid)
            ordered_slides.insert(insert_after_idx + 1,
                                   (new_sld_id, new_rid, new_slide_fname))

            toc_slide_ids_for_section.append(new_sld_id)
            fixes.append(f'TOC page {page_num}: inserted slide{new_slide_num}.xml '
                         f'(sldId={new_sld_id}, rId={new_rid}) — {len(chunk)} sections')

            insert_after_idx += 1
            page_num += 1

    # Update sectionLst for 목차
    _update_section_lst(prs_root, toc_slide_ids_for_section)
    fixes.append(f'목차 section updated: {len(toc_slide_ids_for_section)} TOC slide(s)')

    # Write updated presentation.xml and rels
    all_files['ppt/presentation.xml'] = ET.tostring(
        prs_root, xml_declaration=True, encoding='UTF-8', standalone=True)
    all_files['ppt/_rels/presentation.xml.rels'] = ET.tostring(
        prs_rels_root, xml_declaration=True, encoding='UTF-8', standalone=True)

    # ── Subtitle labels ───────────────────────────────────────────────────────
    # Auto-generate numbered labels from sections when not explicitly provided.
    # Body slides start at index 2 (0=cover, 1=TOC page1, 2+=body).
    if slide_labels is None:
        body_start_idx = 1 + len(toc_slide_ids_for_section)  # after all TOC pages
        slide_labels = {}
        for sec_i, sec_title in enumerate(sections):
            slide_idx = body_start_idx + sec_i  # 0-based index in ordered_slides
            if slide_idx < len(ordered_slides):
                _, _, sp = ordered_slides[slide_idx]
                m = re.search(r'slides/slide(\d+)\.xml', sp)
                if m:
                    snum = int(m.group(1))
                    slide_labels[snum] = (f'{sec_i + 1}. {sec_title}', '')

    if slide_labels:
        for slide_num, (label, desc) in slide_labels.items():
            slide_path = None
            for _, _, sp in ordered_slides:
                m = re.search(r'slides/slide(\d+)\.xml', sp)
                if m and int(m.group(1)) == slide_num:
                    slide_path = f'ppt/{sp}'
                    break
            if slide_path and slide_path in all_files:
                all_files[slide_path] = _update_subtitle_label(
                    all_files[slide_path], label, desc if desc else None)
                desc_preview = f' / "{desc[:30]}..."' if desc else ''
                fixes.append(f'Slide {slide_num} subtitle: "{label}"{desc_preview}')
            else:
                fixes.append(f'WARNING: slide {slide_num} not found, skipping label update')

    # ── Write back ────────────────────────────────────────────────────────────
    with zipfile.ZipFile(pptx_path, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name, data in all_files.items():
            zout.writestr(name, data)

    return fixes


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('pptx')
    ap.add_argument('--sections', nargs='+', help='Section titles in order')
    ap.add_argument('--from-config', help='JSON config file')
    ap.add_argument('--labels', nargs='+',
                    help='slide_num:label:desc  e.g.  3:"L09. AS-IS":"현재 한계 비교"')
    args = ap.parse_args()

    sections = []
    labels = {}

    if args.from_config:
        cfg = json.loads(Path(args.from_config).read_text())
        sections = cfg.get('sections', [])
        labels = {int(k): tuple(v) for k, v in cfg.get('labels', {}).items()}
    else:
        sections = args.sections or []
        if args.labels:
            for item in args.labels:
                parts = item.split(':', 2)
                if len(parts) == 3:
                    labels[int(parts[0])] = (parts[1].strip('"'), parts[2].strip('"'))

    if not sections:
        print('ERROR: no sections provided')
        sys.exit(1)

    fixes = rebuild_toc(args.pptx, sections, labels if labels else None)
    print(f'✅ TOC rebuilt: {len(sections)} sections across '
          f'{(len(sections) - 1) // ITEMS_PER_PAGE + 1} page(s)')
    for f in fixes:
        print(f'  {f}')
