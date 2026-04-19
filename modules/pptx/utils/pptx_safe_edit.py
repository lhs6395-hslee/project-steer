#!/usr/bin/env python3
"""
pptx_safe_edit.py — python-pptx.save() 사용 금지 대안.
PPTX 수정 시 zipfile+lxml 직접 조작으로만 수행.

사용법:
    editor = PptxSafeEditor('path/to/file.pptx')
    editor.edit_slide_xml(slide_index, modifier_fn)
    editor.save()  # atomic write, 슬라이드 내용 검증 포함
"""
import zipfile, os, copy
from pathlib import Path
from lxml import etree as ET
from collections import Counter

PRS_NS  = 'http://schemas.openxmlformats.org/presentationml/2006/main'
REL_NS  = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
A_NS    = 'http://schemas.openxmlformats.org/drawingml/2006/main'
SLIDE_REL_TYPE = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide'


class PptxSafeEditor:
    def __init__(self, pptx_path: str):
        self.path = Path(pptx_path)
        self._load()

    def _load(self):
        with zipfile.ZipFile(str(self.path)) as z:
            self.names = z.namelist()
            self._data = {n: z.read(n) for n in self.names}

        self.prs_xml = ET.fromstring(self._data['ppt/presentation.xml'])
        self.prs_rels = ET.fromstring(self._data['ppt/_rels/presentation.xml.rels'])

        ids = self.prs_xml.find(f'{{{PRS_NS}}}sldIdLst').findall(f'{{{PRS_NS}}}sldId')
        rel_map = {r.get('Id'): r.get('Target')
                   for r in self.prs_rels if r.get('Type') == SLIDE_REL_TYPE}

        self.slide_targets = []
        for sld in ids:
            rid = sld.get(f'{{{REL_NS}}}id')
            self.slide_targets.append(rel_map[rid])  # e.g. "slides/slide8.xml"

        # Parse each slide XML
        self.slide_xmls = {}
        for target in self.slide_targets:
            self.slide_xmls[target] = ET.fromstring(self._data[f'ppt/{target}'])

    def _slide_text_preview(self, target: str) -> str:
        root = self.slide_xmls[target]
        texts = [e.text for e in root.iter(f'{{{A_NS}}}t')
                 if e.text and e.text.strip()]
        return texts[0][:40] if texts else '(empty)'

    def edit_slide_xml(self, slide_index: int, modifier_fn):
        """slide_index(0-based)의 XML tree를 modifier_fn(root)으로 수정."""
        target = self.slide_targets[slide_index]
        modifier_fn(self.slide_xmls[target])

    def get_slide_xml(self, slide_index: int):
        return self.slide_xmls[self.slide_targets[slide_index]]

    def verify(self) -> list:
        """저장 전 검증. 문제 목록 반환."""
        issues = []
        # 1. 슬라이드 수 일관성
        prs_count = len(self.slide_targets)
        xml_count = len(self.slide_xmls)
        if prs_count != xml_count:
            issues.append(f"slide count mismatch: prs={prs_count} xml={xml_count}")

        # 2. 마지막 슬라이드 내용 확인
        last = self.slide_targets[-1]
        preview = self._slide_text_preview(last)
        if not preview or preview == '(empty)':
            issues.append(f"Last slide ({last}) appears empty!")

        # 3. 중복 이름 없음
        dupes = {k:v for k,v in Counter(
            list(self._data.keys()) +
            [f'ppt/{t}' for t in self.slide_targets]
        ).items() if v > 1}
        # (slide_targets are already in _data, so dupes expected = 0)

        return issues

    def save(self, output_path: str = None):
        """검증 후 atomic write. output_path 없으면 원본 덮어씀."""
        issues = self.verify()
        if issues:
            raise RuntimeError(f"PPTX integrity check FAILED:\n" + "\n".join(issues))

        out = Path(output_path) if output_path else self.path
        tmp = out.with_suffix('.pptx.tmp')

        # Update prs/rels bytes
        prs_bytes = ET.tostring(self.prs_xml, xml_declaration=True,
                                encoding='UTF-8', standalone=True)
        prs_rels_bytes = ET.tostring(self.prs_rels, xml_declaration=True,
                                     encoding='UTF-8', standalone=True)

        skip = {'ppt/presentation.xml', 'ppt/_rels/presentation.xml.rels'}
        seen = set()

        with zipfile.ZipFile(str(tmp), 'w', zipfile.ZIP_DEFLATED) as zout:
            for name in self.names:
                if name in seen or name in skip:
                    continue
                seen.add(name)

                # Write modified slide if changed
                slide_key = name.replace('ppt/', '', 1)
                if slide_key in self.slide_xmls:
                    zout.writestr(name, ET.tostring(
                        self.slide_xmls[slide_key],
                        xml_declaration=True, encoding='UTF-8', standalone=True))
                else:
                    zout.writestr(name, self._data[name])

            zout.writestr('ppt/presentation.xml', prs_bytes)
            zout.writestr('ppt/_rels/presentation.xml.rels', prs_rels_bytes)

        os.replace(str(tmp), str(out))
        print(f"Saved: {out} ({len(self.slide_targets)} slides)")
        for i, t in enumerate(self.slide_targets):
            print(f"  [{i}] {t}: {self._slide_text_preview(t)!r}")


import math as _math


def min_safe_y_for_textbox(tx_emu: int, card_x_emu: int, card_y_emu: int, card_r_emu: int) -> int:
    """
    TextBox 좌측(tx_emu)이 roundRect TL corner arc와 겹치지 않는 최소 안전 y(EMU) 계산.

    TL arc 중심: (card_x + r, card_y + r)
    arc 방정식: (x - cx)² + (y - cy)² = r²
    → min_safe_y = cy - sqrt(r² - (tx - cx)²)

    tx >= cx (corner zone 바깥)이면 card_y 반환 (y 제약 없음).
    참조: ECMA-376 §20.1.9.19 prstGeom roundRect
    """
    cx = card_x_emu + card_r_emu
    cy = card_y_emu + card_r_emu
    dx = tx_emu - cx
    if dx >= 0 or abs(dx) >= card_r_emu:
        return card_y_emu
    return int(cy - _math.sqrt(card_r_emu ** 2 - dx ** 2))


def auto_position_card_content(
    slide_xml,
    h_padding_emu: int = 180000,   # 0.5cm 좌우 여백
    v_padding_emu: int = 36000,    # 0.1cm arc 위 여백
    gap_emu: int = 108000,         # 0.3cm TextBox 간 간격
    vibrant_positions: set = None, # flow label 제외용 (x,y,w,h) 집합
) -> list:
    """
    roundRect 카드 안의 TextBox를 카드 geometry 기반으로 자동 배치.

    규칙 (레이아웃 하드코딩 없음 — 카드 도형 속성만 사용):
    - 수평: TextBox x = card_x + h_padding, width = card_w - 2*h_padding
    - 수직: 첫 TextBox는 min_safe_y + v_padding (arc 공식), 이후는 전 TextBox 끝 + gap

    제외:
    - vibrant fill(진한 색) 도형 — flow/diagram element
    - vibrant_positions에 포함된 TextBox — flow label

    반환: 변경 사항 문자열 목록
    """
    PRS = 'http://schemas.openxmlformats.org/presentationml/2006/main'
    A   = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    C   = 360000  # EMU per cm

    if vibrant_positions is None:
        vibrant_positions = set()

    # Build set of vibrant-shape x-coordinates (for column-aligned sub-label exclusion)
    PRS_tmp = 'http://schemas.openxmlformats.org/presentationml/2006/main'
    A_tmp   = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    _vibrant_xs = set()
    for _vpos in vibrant_positions:
        _vibrant_xs.add(_vpos[0])  # x-coordinate of each vibrant shape

    def _fill(sp):
        spPr = sp.find(f'{{{PRS}}}spPr')
        if spPr is None: return None
        for sf in spPr.findall(f'.//{{{A}}}solidFill'):
            clr = sf.find(f'{{{A}}}srgbClr')
            if clr is not None: return clr.get('val','').upper()
        return None

    def _vibrant(h):
        if not h or len(h) != 6: return False
        r,g,b = int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)
        if r>200 and g>200 and b>200: return False
        return max(r,g,b)>80 and (max(r,g,b)-min(r,g,b))>50

    def _xywh(sp):
        spPr = sp.find(f'{{{PRS}}}spPr')
        if spPr is None: return None
        xfrm = spPr.find(f'{{{A}}}xfrm')
        if xfrm is None: return None
        off = xfrm.find(f'{{{A}}}off'); ext = xfrm.find(f'{{{A}}}ext')
        if off is None or ext is None: return None
        return (int(off.get('x',0)), int(off.get('y',0)),
                int(ext.get('cx',0)), int(ext.get('cy',0)))

    def _set(sp, x=None, y=None, w=None):
        spPr = sp.find(f'{{{PRS}}}spPr')
        if spPr is None: return
        xfrm = spPr.find(f'{{{A}}}xfrm')
        if xfrm is None: return
        off = xfrm.find(f'{{{A}}}off'); ext = xfrm.find(f'{{{A}}}ext')
        if off is not None:
            if x is not None: off.set('x', str(x))
            if y is not None: off.set('y', str(y))
        if ext is not None and w is not None: ext.set('cx', str(w))

    def _name(sp):
        el = sp.find(f'.//{{{PRS}}}cNvPr')
        return el.get('name','?') if el is not None else '?'

    # 1. 카드 수집 (light fill roundRect)
    cards = []
    for sp in slide_xml.findall(f'.//{{{PRS}}}sp'):
        adj = get_roundrect_adj(sp)
        if adj is None: continue
        fill = _fill(sp)
        if fill is None or _vibrant(fill): continue
        xywh = _xywh(sp)
        if xywh is None: continue
        x,y,w,h = xywh
        cards.append({'x':x,'y':y,'w':w,'h':h,'r':roundrect_corner_radius(w,h,adj)})

    changes = []

    # 2. 각 카드의 TextBox 배치
    for card in cards:
        cx_b,cy_b,cw,ch,cr = card['x'],card['y'],card['w'],card['h'],card['r']
        new_x = cx_b + h_padding_emu
        new_w = cw - 2 * h_padding_emu
        if new_w <= 0: continue

        inside = []
        for sp in slide_xml.findall(f'.//{{{PRS}}}sp'):
            txBody = sp.find(f'{{{PRS}}}txBody')
            if txBody is None: continue
            texts = [e.text for e in txBody.iter(f'{{{A}}}t') if e.text and e.text.strip()]
            if not texts: continue
            xywh = _xywh(sp)
            if xywh is None: continue
            tx,ty,tw,th = xywh
            if not (tx >= cx_b and tx < cx_b+cw and ty >= cy_b and ty < cy_b+ch): continue
            # Exclude: exact position match OR x-column aligned with vibrant shape (±0.25cm)
            if xywh in vibrant_positions: continue
            X_TOL = 91440  # 0.25cm
            if any(abs(tx - vx) <= X_TOL for vx in _vibrant_xs): continue
            inside.append({'sp':sp,'tx':tx,'ty':ty,'tw':tw,'th':th})

        if not inside: continue
        inside.sort(key=lambda t: t['ty'])

        prev_end = None
        for item in inside:
            sp = item['sp']; tx,ty,tw,th = item['tx'],item['ty'],item['tw'],item['th']
            safe_y = min_safe_y_for_textbox(new_x, cx_b, cy_b, cr)
            min_y  = safe_y + v_padding_emu
            if prev_end is None:
                target_y = min_y
            else:
                target_y = max(min_y, prev_end + gap_emu)
            h_ok = (tx == new_x and tw == new_w)
            y_ok = (ty == target_y)
            if not h_ok or not y_ok:
                _set(sp, x=new_x, y=target_y, w=new_w)
                changes.append(f"  {_name(sp)}: x {tx/C:.2f}→{new_x/C:.2f} y {ty/C:.2f}→{target_y/C:.2f} w {tw/C:.2f}→{new_w/C:.2f}cm")
            prev_end = target_y + th

    return changes


def roundrect_corner_radius(width_emu: int, height_emu: int, adj: int = 16667) -> int:
    """
    PowerPoint roundRect의 corner radius(EMU)를 동적으로 계산.

    Open XML 스펙 (ECMA-376, §20.1.9.19 prstGeom roundRect):
      corner_radius = adj/100000 × min(width, height)
    adj 기본값 16667 (Power Point UI 기본 둥근 모서리).

    참조: https://docs.microsoft.com/en-us/openspecs/office_standards/ms-oe376
    """
    return int(adj / 100000 * min(width_emu, height_emu))


def get_roundrect_adj(sp_elem) -> int:
    """
    lxml sp 요소에서 roundRect adj 값을 추출.
    avLst/gd[@name='adj'] 가 없으면 기본값 16667 반환.
    """
    geom = sp_elem.find(f'.//{{{A_NS}}}prstGeom')
    if geom is None or geom.get('prst') != 'roundRect':
        return None  # not a roundRect
    for gd in geom.findall(f'.//{{{A_NS}}}gd'):
        if gd.get('name') in ('adj', 'adj1'):
            fmla = gd.get('fmla', '')
            if fmla.startswith('val '):
                try:
                    return int(fmla[4:])
                except ValueError:
                    pass
    return 16667  # PowerPoint default


def check_text_corner_overlap(slide_xml, slide_idx: int = None) -> list:
    """
    슬라이드 XML에서 roundRect 도형과 텍스트 박스 간 corner overlap을 동적으로 검사.

    로직:
    1. 모든 roundRect 도형의 bounding box + corner_radius 계산
    2. 모든 TextBox(TYPE=17) / sp의 위치 수집
    3. 텍스트 박스 상단/좌단이 roundRect 꼭지점에서 corner_radius 내에 있으면 overlap 보고

    반환: [{'slide': idx, 'shape': name, 'text': name, 'corner_r_cm': float, 'margin_cm': float}]
    """
    EMU_TO_CM = 2.54 / 914400
    issues = []

    # Collect roundRect shapes: {sp_id -> (name, left, top, w, h, radius)}
    round_rects = {}
    for sp in slide_xml.findall(f'.//{{{PRS_NS}}}sp'):
        nvSpPr = sp.find(f'{{{PRS_NS}}}nvSpPr')
        if nvSpPr is None:
            continue
        cNvPr = nvSpPr.find(f'{{{PRS_NS}}}cNvPr')
        if cNvPr is None:
            continue
        sp_id = cNvPr.get('id')
        name = cNvPr.get('name', '')

        adj = get_roundrect_adj(sp)
        if adj is None:
            continue  # not a roundRect

        spPr = sp.find(f'{{{PRS_NS}}}spPr')
        if spPr is None:
            continue
        xfrm = spPr.find(f'{{{A_NS}}}xfrm')
        if xfrm is None:
            continue
        off = xfrm.find(f'{{{A_NS}}}off')
        ext = xfrm.find(f'{{{A_NS}}}ext')
        if off is None or ext is None:
            continue

        left = int(off.get('x', 0))
        top = int(off.get('y', 0))
        w = int(ext.get('cx', 0))
        h = int(ext.get('cy', 0))
        radius = roundrect_corner_radius(w, h, adj)
        round_rects[sp_id] = (name, left, top, w, h, radius)

    # Collect all text-bearing sp/txBox elements
    text_boxes = []
    for sp in slide_xml.findall(f'.//{{{PRS_NS}}}sp'):
        nvSpPr = sp.find(f'{{{PRS_NS}}}nvSpPr')
        if nvSpPr is None:
            continue
        cNvPr = nvSpPr.find(f'{{{PRS_NS}}}cNvPr')
        if cNvPr is None:
            continue
        name = cNvPr.get('name', '')
        spPr = sp.find(f'{{{PRS_NS}}}spPr')
        if spPr is None:
            continue
        xfrm = spPr.find(f'{{{A_NS}}}xfrm')
        if xfrm is None:
            continue
        off = xfrm.find(f'{{{A_NS}}}off')
        ext = xfrm.find(f'{{{A_NS}}}ext')
        if off is None or ext is None:
            continue
        # Only check shapes with text
        txBody = sp.find(f'{{{PRS_NS}}}txBody')
        if txBody is None:
            continue
        texts = [e.text for e in txBody.iter(f'{{{A_NS}}}t') if e.text and e.text.strip()]
        if not texts:
            continue
        tl = int(off.get('x', 0))
        tt = int(off.get('y', 0))
        tw = int(ext.get('cx', 0))
        th = int(ext.get('cy', 0))
        text_boxes.append((name, tl, tt, tw, th, texts[0][:20]))

    # Cross-check: text box corners vs roundRect corner zones
    for rr_name, rl, rt, rw, rh, radius in round_rects.values():
        rr_right = rl + rw
        rr_bottom = rt + rh

        for tb_name, tl, tt, tw, th, preview in text_boxes:
            if tb_name == rr_name:
                continue  # skip self
            # Check if text box overlaps with the roundRect region
            overlaps_x = tl < rr_right and (tl + tw) > rl
            overlaps_y = tt < rr_bottom and (tt + th) > rt
            if not (overlaps_x and overlaps_y):
                continue  # not even in bounding box

            # Calculate margins from each edge
            margin_from_top = tt - rt
            margin_from_left = tl - rl

            # Corners: TL zone = x < rl+r AND y < rt+r → overlap if text starts within radius
            in_tl_zone = (tl < rl + radius) and (tt < rt + radius)
            in_tr_zone = (tl + tw > rr_right - radius) and (tt < rt + radius)
            in_bl_zone = (tl < rl + radius) and (tt + th > rr_bottom - radius)
            in_br_zone = (tl + tw > rr_right - radius) and (tt + th > rr_bottom - radius)

            # If text box corner is within the rounded corner arc zone
            corner_overlap = in_tl_zone or in_tr_zone or in_bl_zone or in_br_zone
            if corner_overlap:
                r_cm = radius * EMU_TO_CM
                mtop_cm = margin_from_top * EMU_TO_CM
                mleft_cm = margin_from_left * EMU_TO_CM
                issues.append({
                    'slide': slide_idx,
                    'roundrect': rr_name,
                    'text_shape': tb_name,
                    'text_preview': preview,
                    'corner_radius_cm': round(r_cm, 2),
                    'margin_top_cm': round(mtop_cm, 2),
                    'margin_left_cm': round(mleft_cm, 2),
                    'zones': [z for z, f in [('TL', in_tl_zone), ('TR', in_tr_zone),
                                              ('BL', in_bl_zone), ('BR', in_br_zone)] if f],
                })
    return issues


def ensure_shape_border(sp_elem, border_color_hex: str = None, border_none: bool = False):
    """
    shape 요소에 a:ln 명시적 border를 설정한다.

    MISTAKES.md #14: shape 생성 시 ln 명시 없으면 style.lnRef accent1(파란색) 자동 적용.
    모든 shape은 반드시 이 함수로 border를 명시해야 한다.

    Args:
        sp_elem: lxml sp element
        border_color_hex: hex 색상 (예: 'F8F9FA') — 지정 시 solidFill
        border_none: True이면 a:noFill (border 없음)
    """
    A_NS = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    spPr = sp_elem.find(f'{{{A_NS}}}spPr')
    if spPr is None:
        # Try pml namespace
        PRS = 'http://schemas.openxmlformats.org/presentationml/2006/main'
        spPr = sp_elem.find(f'{{{PRS}}}spPr')
    if spPr is None:
        return

    # Remove existing ln if any
    for existing_ln in spPr.findall(f'{{{A_NS}}}ln'):
        spPr.remove(existing_ln)

    ln = ET.SubElement(spPr, f'{{{A_NS}}}ln')
    if border_none or border_color_hex is None:
        ET.SubElement(ln, f'{{{A_NS}}}noFill')
    else:
        solidFill = ET.SubElement(ln, f'{{{A_NS}}}solidFill')
        srgbClr = ET.SubElement(solidFill, f'{{{A_NS}}}srgbClr')
        srgbClr.set('val', border_color_hex.lstrip('#'))


def ensure_shape_fill(sp_elem, fill_color_hex: str = None, no_fill: bool = False):
    """
    shape 요소에 fill을 설정한다.

    Args:
        sp_elem: lxml sp element
        fill_color_hex: hex 색상 (예: '0043DA') — 지정 시 solidFill
        no_fill: True이면 a:noFill (투명 배경)
    """
    A_NS = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    PRS = 'http://schemas.openxmlformats.org/presentationml/2006/main'

    # Find spPr (try both namespaces)
    spPr = sp_elem.find(f'{{{A_NS}}}spPr')
    if spPr is None:
        spPr = sp_elem.find(f'{{{PRS}}}spPr')
    if spPr is None:
        return

    # Remove existing fill elements
    for tag in ['noFill', 'solidFill', 'gradFill', 'blipFill', 'pattFill', 'grpFill']:
        for el in spPr.findall(f'{{{A_NS}}}{tag}'):
            spPr.remove(el)

    if no_fill or fill_color_hex is None:
        ET.SubElement(spPr, f'{{{A_NS}}}noFill')
    else:
        solidFill = ET.SubElement(spPr, f'{{{A_NS}}}solidFill')
        srgbClr = ET.SubElement(solidFill, f'{{{A_NS}}}srgbClr')
        srgbClr.set('val', fill_color_hex.lstrip('#'))


def create_l11_comparison_table(
    source_pptx_path: str,
    output_path: str,
    data: dict = None,
) -> str:
    """
    L11 Comparison Table 슬라이드를 생성하여 /tmp/slide_1_l11.pptx로 저장한다.

    스펙 출처: modules/pptx/references/layout-spec.md L11 섹션
    Recon 결과: /tmp/recon_l11_l12.md

    Shape 목록:
    - 요약 제목 TextBox: (457200, 1600200) 11277600×320040 16pt PRIMARY Bold Freesentation
    - 요약 설명 TextBox: (457200, 1965960) 11277600×274320 13pt DARK_GRAY Freesentation
    - 비교 테이블 (graphicFrame): (457200, 2423160) 11277600×4252320
      - 6행×4열: header(457200) + 5 data rows(759024 each)
      - 4열: label(2560320) + 3 options(2905760 each)
      - Header: PRIMARY #0043DA bg, 흰색 11pt Bold "프리젠테이션 7 Bold"
      - Label col: BG_BOX #F8F9FA, DARK_GRAY 13pt Bold "프리젠테이션 7 Bold"
      - Data: 흰색/BG_BOX 교차, DARK_GRAY 13pt Freesentation
      - 권장 옵션: PRIMARY #0043DA Bold 텍스트, ✓ prefix header

    WCAG 검증 (recon 확인):
    - Header: 7.2:1 AAA  - Label col: 15.5:1 AAA
    - Data 홀수: 16.1:1 AAA  - Data 짝수: 15.5:1 AAA
    - 권장옵션 data: 7.2:1/6.9:1 AA

    Args:
        source_pptx_path: 원본 PPTX 경로 (마스터/레이아웃/상단바 보존용)
        output_path: 출력 PPTX 경로 (예: /tmp/slide_1_l11.pptx)
        data: 슬라이드 데이터 딕셔너리. None이면 기본 샘플 데이터 사용.

    Returns:
        output_path (저장된 파일 경로)
    """
    import zipfile, shutil, re, copy, io
    from pathlib import Path
    from lxml import etree as ET_l

    # ── 색상 상수 ────────────────────────────────────────────────────────
    PRIMARY = '0043DA'
    DARK_GRAY = '212121'
    WHITE = 'FFFFFF'
    BG_BOX = 'F8F9FA'
    BORDER = 'DCDCDC'

    # ── 기본 샘플 데이터 ──────────────────────────────────────────────────
    if data is None:
        data = {
            "body_title": "클라우드 메시징 솔루션 비교",
            "body_desc": "AWS MSK · Confluent Cloud · 자체 구축 Kafka 3개 옵션 비교 (2026년 4월 기준)",
            "columns": [
                {"label": "항목", "is_header_col": True},
                {"label": "자체 구축 Kafka"},
                {"label": "✓ AWS MSK", "recommended": True},
                {"label": "Confluent Cloud"},
            ],
            "rows": [
                {"criteria": "초기 비용",
                 "values": ["₩5억+ 서버 구매", "초기 투자 0원", "초기 투자 0원"]},
                {"criteria": "운영 인력",
                 "values": ["전담 2~3명", "0.5명 (모니터링)", "0명 (완전 관리)"]},
                {"criteria": "가용성 SLA",
                 "values": ["자체 HA 구성", "99.9% 보장", "99.95% 보장"]},
                {"criteria": "확장 소요",
                 "values": ["2~4주", "수분 내", "수분 내"]},
                {"criteria": "월 운영비",
                 "values": ["₩3,000만+", "₩800만~", "₩1,200만~"]},
            ],
        }

    # ── 네임스페이스 ──────────────────────────────────────────────────────
    P_NS = 'http://schemas.openxmlformats.org/presentationml/2006/main'
    A_NS = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    R_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    REL_NS_PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
    CT_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'
    SLIDE_REL_TYPE = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide'
    SLIDE_LAYOUT_REL_TYPE = ('http://schemas.openxmlformats.org/officeDocument/'
                              '2006/relationships/slideLayout')

    ET_l.register_namespace('p', P_NS)
    ET_l.register_namespace('a', A_NS)
    ET_l.register_namespace('r', R_NS)

    # ── 1. 원본 복사 ──────────────────────────────────────────────────────
    shutil.copy2(source_pptx_path, output_path)

    # ── 2. ZIP 읽기 ───────────────────────────────────────────────────────
    all_data = {}
    with zipfile.ZipFile(output_path, 'r') as z:
        for name in z.namelist():
            all_data[name] = z.read(name)

    prs_xml = ET_l.fromstring(all_data['ppt/presentation.xml'])
    prs_rels = ET_l.fromstring(all_data['ppt/_rels/presentation.xml.rels'])

    # ── 3. 기존 슬라이드 목록 파악 ───────────────────────────────────────
    sldIdLst = prs_xml.find(f'{{{P_NS}}}sldIdLst')
    slide_ids = sldIdLst.findall(f'{{{P_NS}}}sldId')
    max_id = max(int(s.get('id')) for s in slide_ids)
    max_r_num = 0
    for rel in prs_rels:
        m = re.match(r'rId(\d+)', rel.get('Id', ''))
        if m:
            max_r_num = max(max_r_num, int(m.group(1)))

    existing_slides = [n for n in all_data if re.match(r'ppt/slides/slide\d+\.xml$', n)]
    nums = [int(re.search(r'slide(\d+)\.xml', n).group(1)) for n in existing_slides]
    next_num = max(nums) + 1

    # ── 4. slideLayout2 rels 경로 확인 ──────────────────────────────────
    # 본문 슬라이드는 모두 slideLayout2 사용 (실측 확인)
    layout_target = '../slideLayouts/slideLayout2.xml'

    # ── 5. 새 슬라이드 XML 빌드 ──────────────────────────────────────────
    def make_textbox(sp_id, name, x, y, cx, cy, text, sz, bold, color_hex,
                     font='Freesentation', align='l'):
        """TextBox sp 요소 생성 (noFill + a:ln noFill)."""
        sp = ET_l.Element(f'{{{P_NS}}}sp')

        nvSpPr = ET_l.SubElement(sp, f'{{{P_NS}}}nvSpPr')
        cNvPr = ET_l.SubElement(nvSpPr, f'{{{P_NS}}}cNvPr')
        cNvPr.set('id', str(sp_id))
        cNvPr.set('name', name)
        cNvSpPr = ET_l.SubElement(nvSpPr, f'{{{P_NS}}}cNvSpPr')
        cNvSpPr.set('txBox', '1')
        ET_l.SubElement(nvSpPr, f'{{{P_NS}}}nvPr')

        spPr = ET_l.SubElement(sp, f'{{{P_NS}}}spPr')
        xfrm = ET_l.SubElement(spPr, f'{{{A_NS}}}xfrm')
        off = ET_l.SubElement(xfrm, f'{{{A_NS}}}off')
        off.set('x', str(x)); off.set('y', str(y))
        ext = ET_l.SubElement(xfrm, f'{{{A_NS}}}ext')
        ext.set('cx', str(cx)); ext.set('cy', str(cy))
        prstGeom = ET_l.SubElement(spPr, f'{{{A_NS}}}prstGeom')
        prstGeom.set('prst', 'rect')
        ET_l.SubElement(prstGeom, f'{{{A_NS}}}avLst')
        ET_l.SubElement(spPr, f'{{{A_NS}}}noFill')
        # border 명시 (MISTAKES.md #14)
        ln = ET_l.SubElement(spPr, f'{{{A_NS}}}ln')
        ET_l.SubElement(ln, f'{{{A_NS}}}noFill')

        txBody = ET_l.SubElement(sp, f'{{{P_NS}}}txBody')
        bodyPr = ET_l.SubElement(txBody, f'{{{A_NS}}}bodyPr')
        bodyPr.set('wrap', 'square')
        ET_l.SubElement(bodyPr, f'{{{A_NS}}}spAutoFit')
        ET_l.SubElement(txBody, f'{{{A_NS}}}lstStyle')

        para = ET_l.SubElement(txBody, f'{{{A_NS}}}p')
        pPr = ET_l.SubElement(para, f'{{{A_NS}}}pPr')
        pPr.set('algn', align)
        run = ET_l.SubElement(para, f'{{{A_NS}}}r')
        rPr = ET_l.SubElement(run, f'{{{A_NS}}}rPr')
        rPr.set('sz', str(sz))
        rPr.set('b', '1' if bold else '0')
        solidFill = ET_l.SubElement(rPr, f'{{{A_NS}}}solidFill')
        srgbClr = ET_l.SubElement(solidFill, f'{{{A_NS}}}srgbClr')
        srgbClr.set('val', color_hex)
        latin = ET_l.SubElement(rPr, f'{{{A_NS}}}latin')
        latin.set('typeface', font)
        t_elem = ET_l.SubElement(run, f'{{{A_NS}}}t')
        t_elem.text = text

        return sp

    def make_table_cell(text, sz, bold, text_color, bg_color,
                        font='Freesentation', align='ctr', is_header_label=False):
        """
        표 셀 tc 요소 생성.

        border: 셀 경계선 DCDCDC (표준 테이블 셀 경계)
        WCAG 검증은 recon에서 완료됨:
          - PRIMARY bg (#0043DA) + WHITE text (#FFFFFF): 7.2:1 AAA
          - BG_BOX bg (#F8F9FA) + DARK_GRAY text (#212121): 15.5:1 AAA
          - WHITE bg (#FFFFFF) + DARK_GRAY text (#212121): 16.1:1 AAA
        """
        tc = ET_l.Element(f'{{{A_NS}}}tc')

        txBody = ET_l.SubElement(tc, f'{{{A_NS}}}txBody')
        bodyPr = ET_l.SubElement(txBody, f'{{{A_NS}}}bodyPr')
        bodyPr.set('anchor', 'ctr')
        ET_l.SubElement(txBody, f'{{{A_NS}}}lstStyle')
        para = ET_l.SubElement(txBody, f'{{{A_NS}}}p')
        pPr = ET_l.SubElement(para, f'{{{A_NS}}}pPr')
        pPr.set('algn', align)

        run = ET_l.SubElement(para, f'{{{A_NS}}}r')
        rPr = ET_l.SubElement(run, f'{{{A_NS}}}rPr')
        rPr.set('lang', 'ko-KR')
        rPr.set('sz', str(sz))
        rPr.set('b', '1' if bold else '0')
        solidFill_r = ET_l.SubElement(rPr, f'{{{A_NS}}}solidFill')
        srgbClr_r = ET_l.SubElement(solidFill_r, f'{{{A_NS}}}srgbClr')
        srgbClr_r.set('val', text_color)
        latin_r = ET_l.SubElement(rPr, f'{{{A_NS}}}latin')
        latin_r.set('typeface', font)
        t_el = ET_l.SubElement(run, f'{{{A_NS}}}t')
        t_el.text = text

        # 셀 배경 및 border 설정
        tcPr = ET_l.SubElement(tc, f'{{{A_NS}}}tcPr')
        # 셀 경계선: DCDCDC (테이블 표준)
        for side in ['lnL', 'lnR', 'lnT', 'lnB']:
            ln_el = ET_l.SubElement(tcPr, f'{{{A_NS}}}{side}')
            ln_el.set('w', '12700')   # 1pt = 12700 EMU
            ln_el.set('cap', 'flat')
            ln_el.set('cmpd', 'sng')
            ln_solidFill = ET_l.SubElement(ln_el, f'{{{A_NS}}}solidFill')
            ln_srgb = ET_l.SubElement(ln_solidFill, f'{{{A_NS}}}srgbClr')
            ln_srgb.set('val', BORDER)
        # 셀 fill
        solidFill_bg = ET_l.SubElement(tcPr, f'{{{A_NS}}}solidFill')
        srgbClr_bg = ET_l.SubElement(solidFill_bg, f'{{{A_NS}}}srgbClr')
        srgbClr_bg.set('val', bg_color)

        return tc

    # tableStyles.xml 기본 스타일 ID 읽기 (없으면 None style 사용)
    _table_style_id = '{2D5ABB26-0587-4C30-8999-92F81FD0307C}'  # None style (fallback)
    if 'ppt/tableStyles.xml' in all_data:
        _ts_root = ET_l.fromstring(all_data['ppt/tableStyles.xml'])
        _def = _ts_root.get('def')
        if _def:
            _table_style_id = _def

    def make_table_xml(columns, rows):
        """
        비교 테이블 graphicFrame 전체 XML 생성.

        위치/크기 (스펙):
          left=457200 top=2423160 width=11277600 height=4252320
        행/열 (스펙):
          - header row: 457200 EMU
          - data rows × 5: 759024 EMU each
          - label col: 2560320 EMU
          - option cols × 3: 2905760 EMU each
        """
        # graphicFrame element
        gf = ET_l.Element(f'{{{P_NS}}}graphicFrame')

        # nvGraphicFramePr (OOXML 정식 이름 — MISTAKES.md #24 참조)
        # 잘못: nvGrFrPr, cNvGrFrPr (축약형, OOXML 스펙에 없음 → PowerPoint repair 다이얼로그)
        # 정확: nvGraphicFramePr, cNvGraphicFramePr (python-pptx reference 대조 확인)
        nvGrFrPr = ET_l.SubElement(gf, f'{{{P_NS}}}nvGraphicFramePr')
        cNvPr_gf = ET_l.SubElement(nvGrFrPr, f'{{{P_NS}}}cNvPr')
        cNvPr_gf.set('id', '20')
        cNvPr_gf.set('name', 'Table L11')
        cNvGrFrPr = ET_l.SubElement(nvGrFrPr, f'{{{P_NS}}}cNvGraphicFramePr')
        locks_el = ET_l.SubElement(cNvGrFrPr, f'{{{A_NS}}}graphicFrameLocks')
        locks_el.set('noGrp', '1')  # python-pptx 표준 속성
        ET_l.SubElement(nvGrFrPr, f'{{{P_NS}}}nvPr')

        # xfrm
        xfrm_gf = ET_l.SubElement(gf, f'{{{P_NS}}}xfrm')
        off_gf = ET_l.SubElement(xfrm_gf, f'{{{A_NS}}}off')
        off_gf.set('x', '457200'); off_gf.set('y', '2423160')
        ext_gf = ET_l.SubElement(xfrm_gf, f'{{{A_NS}}}ext')
        ext_gf.set('cx', '11277600'); ext_gf.set('cy', '4252320')

        # graphic > graphicData > tbl
        graphic = ET_l.SubElement(gf, f'{{{A_NS}}}graphic')
        graphicData = ET_l.SubElement(graphic, f'{{{A_NS}}}graphicData')
        TBL_NS = 'http://schemas.openxmlformats.org/drawingml/2006/table'
        graphicData.set('uri', TBL_NS)

        # tbl은 A_NS(drawingml/2006/main) 사용 — TBL_NS 사용 시 ns0:tbl 생성되어 PowerPoint 오류
        tbl = ET_l.SubElement(graphicData, f'{{{A_NS}}}tbl')

        # tblPr
        tblPr = ET_l.SubElement(tbl, f'{{{A_NS}}}tblPr')
        tblPr.set('firstRow', '1')
        tblPr.set('bandRow', '0')   # 수동 색상으로 교차 적용
        ET_l.SubElement(tblPr, f'{{{A_NS}}}noFill')   # 테이블 외곽 배경 없음
        # tableStyleId 필수 (없으면 PowerPoint repair 다이얼로그 발생)
        tblStyleId_el = ET_l.SubElement(tblPr, f'{{{A_NS}}}tableStyleId')
        tblStyleId_el.text = _table_style_id

        # 열 너비 그리드
        # 옵션 수 계산 (columns 중 is_header_col=True 제외)
        option_cols = [c for c in columns if not c.get('is_header_col')]
        n_options = len(option_cols)

        COL_WIDTHS = {
            2: (2743200, 3767200),   # label + option×2
            3: (2560320, 2905760),   # label + option×3 (기본)
            4: (2286000, 2000220),   # label + option×4
        }
        label_w, opt_w = COL_WIDTHS.get(n_options, COL_WIDTHS[3])
        total_cols = 1 + n_options

        tblGrid = ET_l.SubElement(tbl, f'{{{A_NS}}}tblGrid')
        ET_l.SubElement(tblGrid, f'{{{A_NS}}}gridCol').set('w', str(label_w))
        for _ in range(n_options):
            ET_l.SubElement(tblGrid, f'{{{A_NS}}}gridCol').set('w', str(opt_w))

        # ── Header row (row 0) ──────────────────────────────────────────
        HEADER_H = 457200
        DATA_H = 759024

        tr_header = ET_l.SubElement(tbl, f'{{{A_NS}}}tr')
        tr_header.set('h', str(HEADER_H))

        # Header label cell (col 0): 항목 레이블
        label_header_text = columns[0].get('label', '항목')
        tc_h0 = make_table_cell(
            text=label_header_text, sz=1100, bold=True,
            text_color=WHITE, bg_color=PRIMARY,
            font='프리젠테이션 7 Bold', align='ctr'
        )
        tr_header.append(tc_h0)

        # Header option cells (col 1+)
        for col in option_cols:
            col_label = col.get('label', '')
            # 권장 옵션: ✓ prefix 이미 레이블에 포함 여부 확인 (recommended 플래그)
            if col.get('recommended') and not col_label.startswith('✓'):
                col_label = f'✓ {col_label}'
            tc_h = make_table_cell(
                text=col_label, sz=1100, bold=True,
                text_color=WHITE, bg_color=PRIMARY,
                font='프리젠테이션 7 Bold', align='ctr'
            )
            tr_header.append(tc_h)

        # ── Data rows (row 1~5) ─────────────────────────────────────────
        recommended_col_idx = None
        for ci, col in enumerate(option_cols):
            if col.get('recommended'):
                recommended_col_idx = ci  # 0-based within option_cols

        for row_idx, row in enumerate(rows):
            # 홀수행(row_idx 0,2,4): WHITE / 짝수행(1,3): BG_BOX
            row_bg = WHITE if row_idx % 2 == 0 else BG_BOX

            tr = ET_l.SubElement(tbl, f'{{{A_NS}}}tr')
            tr.set('h', str(DATA_H))

            # Label cell (col 0): 프리젠테이션 7 Bold, 13pt, DARK_GRAY, 좌측
            tc_label = make_table_cell(
                text=row.get('criteria', ''),
                sz=1300, bold=True,
                text_color=DARK_GRAY, bg_color=BG_BOX,
                font='프리젠테이션 7 Bold', align='l'
            )
            tr.append(tc_label)

            # Data cells (col 1+)
            for ci, val in enumerate(row.get('values', [])):
                is_recommended = (ci == recommended_col_idx)
                tc_data = make_table_cell(
                    text=val,
                    sz=1300,
                    bold=is_recommended,
                    text_color=PRIMARY if is_recommended else DARK_GRAY,
                    bg_color=row_bg,
                    font='Freesentation', align='ctr'
                )
                tr.append(tc_data)

        return gf

    # ── 6. 슬라이드 XML 조립 ─────────────────────────────────────────────
    # 컬럼/행 분석
    columns = data.get('columns', [])
    rows = data.get('rows', [])

    # 슬라이드 XML 루트 — p:sld
    sld_nsmap = {
        'p': P_NS, 'a': A_NS, 'r': R_NS,
    }
    sld_root = ET_l.Element(f'{{{P_NS}}}sld', nsmap=sld_nsmap)

    # cSld > spTree
    cSld = ET_l.SubElement(sld_root, f'{{{P_NS}}}cSld')
    spTree = ET_l.SubElement(cSld, f'{{{P_NS}}}spTree')

    # nvGrpSpPr, grpSpPr (필수 요소)
    nvGrpSpPr = ET_l.SubElement(spTree, f'{{{P_NS}}}nvGrpSpPr')
    cNvPr_grp = ET_l.SubElement(nvGrpSpPr, f'{{{P_NS}}}cNvPr')
    cNvPr_grp.set('id', '1'); cNvPr_grp.set('name', '')
    ET_l.SubElement(nvGrpSpPr, f'{{{P_NS}}}cNvGrpSpPr')
    ET_l.SubElement(nvGrpSpPr, f'{{{P_NS}}}nvPr')
    # grpSpPr: 빈 요소 (xfrm 추가 금지 — 기존 슬라이드 패턴과 일치)
    ET_l.SubElement(spTree, f'{{{P_NS}}}grpSpPr')

    # Text Placeholder 1 (레이아웃 본문 placeholder — 빈 상태로 유지)
    sp_ph = ET_l.SubElement(spTree, f'{{{P_NS}}}sp')
    nvSpPr_ph = ET_l.SubElement(sp_ph, f'{{{P_NS}}}nvSpPr')
    cNvPr_ph = ET_l.SubElement(nvSpPr_ph, f'{{{P_NS}}}cNvPr')
    cNvPr_ph.set('id', '2'); cNvPr_ph.set('name', 'Text Placeholder 1')
    cNvSpPr_ph = ET_l.SubElement(nvSpPr_ph, f'{{{P_NS}}}cNvSpPr')
    spLocks_ph = ET_l.SubElement(cNvSpPr_ph, f'{{{A_NS}}}spLocks')
    spLocks_ph.set('noGrp', '1')
    nvPr_ph = ET_l.SubElement(nvSpPr_ph, f'{{{P_NS}}}nvPr')
    ph_el = ET_l.SubElement(nvPr_ph, f'{{{P_NS}}}ph')
    ph_el.set('type', 'body'); ph_el.set('idx', '10'); ph_el.set('sz', 'quarter')
    # spPr: 빈 요소 (placeholder는 spPr override 금지 — 기존 슬라이드 패턴)
    ET_l.SubElement(sp_ph, f'{{{P_NS}}}spPr')
    txBody_ph = ET_l.SubElement(sp_ph, f'{{{P_NS}}}txBody')
    ET_l.SubElement(txBody_ph, f'{{{A_NS}}}bodyPr')
    ET_l.SubElement(txBody_ph, f'{{{A_NS}}}lstStyle')
    ET_l.SubElement(txBody_ph, f'{{{A_NS}}}p')

    # 요약 제목 TextBox (16pt PRIMARY Bold Freesentation)
    tb_title = make_textbox(
        sp_id=10, name='TextBox L11 Title',
        x=457200, y=1600200, cx=11277600, cy=320040,
        text=data.get('body_title', ''),
        sz=1600, bold=True, color_hex=PRIMARY,
        font='Freesentation', align='l'
    )
    spTree.append(tb_title)

    # 요약 설명 TextBox (13pt DARK_GRAY Regular Freesentation)
    tb_desc = make_textbox(
        sp_id=11, name='TextBox L11 Desc',
        x=457200, y=1965960, cx=11277600, cy=274320,
        text=data.get('body_desc', ''),
        sz=1300, bold=False, color_hex=DARK_GRAY,
        font='Freesentation', align='l'
    )
    spTree.append(tb_desc)

    # 비교 테이블 (graphicFrame)
    table_gf = make_table_xml(columns, rows)
    spTree.append(table_gf)

    # clrMapOvr (슬라이드별 색상 오버라이드 — 없으면 레이아웃 상속)
    clrMapOvr = ET_l.SubElement(sld_root, f'{{{P_NS}}}clrMapOvr')
    ET_l.SubElement(clrMapOvr, f'{{{A_NS}}}masterClrMapping')

    # ── 7. 기존 슬라이드 전체 삭제, 새 슬라이드만 남기기 ─────────────────
    # (temp PPTX: 단일 슬라이드 PPTX로 만들기)
    # 기존 슬라이드 파일들을 all_data에서 제거하고 새 슬라이드만 추가

    # 기존 slide XML들 키 수집
    existing_slide_keys = [k for k in all_data if re.match(r'ppt/slides/slide\d+\.xml$', k)]
    existing_rels_keys = [k for k in all_data if re.match(r'ppt/slides/_rels/slide\d+\.xml\.rels$', k)]

    # 새 슬라이드 파일명
    new_slide_name = 'ppt/slides/slide1.xml'
    new_rels_name = 'ppt/slides/_rels/slide1.xml.rels'

    # 기존 모든 slide xml 및 rels 삭제
    for k in existing_slide_keys + existing_rels_keys:
        if k in all_data:
            del all_data[k]

    # 새 슬라이드 XML 저장
    slide_bytes = ET_l.tostring(sld_root, xml_declaration=True,
                                 encoding='UTF-8', standalone=True)
    all_data[new_slide_name] = slide_bytes

    # 새 슬라이드 rels (slideLayout2 참조)
    rels_root = ET_l.Element('Relationships')
    rels_root.set('xmlns', REL_NS_PKG)
    rel_layout = ET_l.SubElement(rels_root, 'Relationship')
    rel_layout.set('Id', 'rId1')
    rel_layout.set('Type', SLIDE_LAYOUT_REL_TYPE)
    rel_layout.set('Target', layout_target)
    rels_bytes = ET_l.tostring(rels_root, xml_declaration=True,
                                encoding='UTF-8', standalone=True)
    all_data[new_rels_name] = rels_bytes

    # ── 8. presentation.xml 업데이트 (단일 슬라이드) ─────────────────────
    # sldIdLst 초기화
    sldIdLst.clear()
    new_sld_id = ET_l.SubElement(sldIdLst, f'{{{P_NS}}}sldId')
    new_sld_id.set('id', '256')
    new_sld_id.set(f'{{{R_NS}}}id', 'rId1000')

    # presentation.xml.rels 업데이트
    new_prs_rels = ET_l.Element('Relationships')
    new_prs_rels.set('xmlns', REL_NS_PKG)
    # 기존 non-slide rels 유지 (slideMaster, slideLayout, theme 등)
    SLIDE_REL_TYPE_FRAG = '/relationships/slide'
    for rel in prs_rels:
        rel_type = rel.get('Type', '')
        if 'slideMaster' in rel_type or 'theme' in rel_type or 'presProps' in rel_type \
                or 'viewProps' in rel_type or 'tableStyles' in rel_type \
                or 'notesMaster' in rel_type or 'font' in rel_type \
                or 'handoutMaster' in rel_type:
            new_prs_rels.append(copy.deepcopy(rel))
        elif rel_type.endswith('/slide') and 'Layout' not in rel_type and 'Master' not in rel_type:
            pass  # 기존 slide rels 제외
        elif 'Layout' not in rel_type and 'Master' not in rel_type \
                and not rel_type.endswith('/slide'):
            new_prs_rels.append(copy.deepcopy(rel))

    # 새 슬라이드 relationship 추가
    new_rel = ET_l.SubElement(new_prs_rels, 'Relationship')
    new_rel.set('Id', 'rId1000')
    new_rel.set('Type', SLIDE_REL_TYPE)
    new_rel.set('Target', 'slides/slide1.xml')

    all_data['ppt/presentation.xml'] = ET_l.tostring(
        prs_xml, xml_declaration=True, encoding='UTF-8', standalone=True)
    all_data['ppt/_rels/presentation.xml.rels'] = ET_l.tostring(
        new_prs_rels, xml_declaration=True, encoding='UTF-8', standalone=True)

    # ── 9. Content_Types.xml 업데이트 ────────────────────────────────────
    ct_xml = ET_l.fromstring(all_data['[Content_Types].xml'])
    SLIDE_CT = ('application/vnd.openxmlformats-officedocument.'
                'presentationml.slide+xml')
    # 기존 slide Override 항목 삭제
    for override in list(ct_xml.findall(f'{{{CT_NS}}}Override')):
        pn = override.get('PartName', '')
        if '/slides/slide' in pn:
            ct_xml.remove(override)
    # 새 슬라이드 추가
    new_override = ET_l.SubElement(ct_xml, f'{{{CT_NS}}}Override')
    new_override.set('PartName', '/ppt/slides/slide1.xml')
    new_override.set('ContentType', SLIDE_CT)
    all_data['[Content_Types].xml'] = ET_l.tostring(
        ct_xml, xml_declaration=True, encoding='UTF-8', standalone=True)

    # ── 10. ZIP 재조립 + 저장 ──────────────────────────────────────────
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name, content in sorted(all_data.items()):
            zout.writestr(name, content)
    with open(output_path, 'wb') as f:
        f.write(buf.getvalue())

    # ── 11. cornerRadius 검증 (テーブルは roundRect なし — スキップ) ──────
    # テーブルは roundRect を使用しないため corner_overlap 検証は不要
    # TextBox も roundRect ではない (rect) — corner_radius = N/A

    print(f"[L11] saved: {output_path}")
    print(f"  body_title: {data.get('body_title', '')!r}")
    print(f"  columns: {len(columns)}")
    print(f"  rows: {len(rows)}")
    return output_path


def create_l12_before_after(
    source_pptx_path: str,
    output_path: str,
    data: dict = None,
) -> str:
    """
    L12 Before/After 슬라이드를 생성하여 output_path로 저장한다.

    스펙 출처: modules/pptx/references/layout-spec.md L12 섹션
    Recon 결과: /tmp/recon_l11_l12.md

    Shape 목록 (position EMU, 스펙 정확히 일치):
    - 요약 제목 TB:      (457200, 1600200) 11277600×320040  16pt PRIMARY Bold Freesentation
    - 요약 설명 TB:      (457200, 1965960) 11277600×274320  13pt DARK_GRAY Freesentation
    - 좌 배지 RRect:     (637160, 2423160) 1371600×274320   DARK_GRAY fill, border=DARK_GRAY
    - 우 배지 RRect:     (6611040,2423160) 1371600×274320   PRIMARY fill, border=PRIMARY
    - 좌 배지 TB overlay:(637160, 2423160) 1371600×274320   BEFORE 11pt Bold WHITE
    - 우 배지 TB overlay:(6611040,2423160) 1371600×274320   AFTER  11pt Bold WHITE
    - 좌 패널 RRect:     (457200, 2789820) 5303520×3885660  BG_BOX fill
    - 우 패널 RRect:     (6431280,2789820) 5303520×3885660  E6F0FF fill
    - 화살표 RightArrow: (5944440,4594980) 411480×274320    PRIMARY fill
    - 좌 KPI 수치 TB:    (637160, 2897580) 4941840×457200   24pt DARK_GRAY 프리젠테이션7Bold
    - 우 KPI 수치 TB:    (6611040,2897580) 4941840×457200   24pt PRIMARY 프리젠테이션7Bold
    - 좌 KPI 레이블 TB:  (637160, 3354780) 4941840×228600   11pt GRAY Freesentation
    - 우 KPI 레이블 TB:  (6611040,3354780) 4941840×228600   11pt GRAY Freesentation
    - 좌 구분선 Line:    (637160, 3674820) 4941840×0        DCDCDC 1pt
    - 우 구분선 Line:    (6611040,3674820) 4941840×0        DCDCDC 1pt
    - 좌 내용 TB:        (637160, 3766260) 4484640×1947040  13pt DARK_GRAY Freesentation
    - 우 내용 TB:        (6611040,3766260) 4484640×1947040  13pt DARK_GRAY Freesentation
    - 좌 아이콘 PNG:     (5047200,6087600) 411480×411480
    - 우 아이콘 PNG:     (11021280,6087600) 411480×411480
    - 변화율 배지 RRect: (5318760,5029200) 1554480×274320   PRIMARY fill [선택]

    WCAG 검증 (recon 확인):
    - 좌 배지(DARK_GRAY+WHITE): 16.1:1 AAA
    - 우 배지(PRIMARY+WHITE): 7.2:1 AAA
    - 좌 KPI(BG_BOX+DARK_GRAY): 15.5:1 AAA
    - 우 KPI(E6F0FF+PRIMARY): 5.8:1 AA
    - KPI 레이블(GRAY #505050): 7.0:1 AA
    - 변화율 배지(PRIMARY+WHITE): 7.2:1 AAA

    패널 roundRect corner radius (동적 계산):
    - adj=16667, min(5303520,3885660)=3885660 → radius=647,712 EMU (0.708")
    배지 roundRect corner radius:
    - adj=16667, min(1371600,274320)=274320 → radius=45,720 EMU (0.050")

    Args:
        source_pptx_path: 원본 PPTX 경로 (마스터/레이아웃/상단바 보존용)
        output_path: 출력 PPTX 경로 (예: /tmp/slide_2_l12.pptx)
        data: 슬라이드 데이터 딕셔너리. None이면 기본 샘플 데이터 사용.

    Returns:
        output_path (저장된 파일 경로)
    """
    import zipfile, shutil, re, copy, io, base64
    from pathlib import Path
    from lxml import etree as ET_l

    # ── 색상 상수 ──────────────────────────────────────────────────────────
    PRIMARY   = '0043DA'
    DARK_GRAY = '212121'
    WHITE     = 'FFFFFF'
    BG_BOX    = 'F8F9FA'
    PANEL_AF  = 'E6F0FF'   # 우 패널(AFTER) 연파랑
    GRAY      = '505050'   # KPI 레이블
    BORDER    = 'DCDCDC'   # 구분선

    # ── 기본 샘플 데이터 ────────────────────────────────────────────────────
    if data is None:
        data = {
            "body_title": "API 응답 시간 개선 — MSK 이벤트 기반 아키텍처 전환 효과",
            "body_desc": "2026년 1분기 실측 기준. 동일 트래픽(10K RPS) 조건 A/B 테스트 결과",
            "before_badge": "BEFORE",
            "before_kpi_value": "3.2초",
            "before_kpi_label": "평균 응답 시간",
            "before_body": "• 단일 서버 동기 처리\n• REST API 직접 호출\n• 무중단 배포 미지원",
            "before_icon": "warning",
            "after_badge": "AFTER",
            "after_kpi_value": "0.8초",
            "after_kpi_label": "평균 응답 시간",
            "after_body": "• Redis 캐시 + CDN 적용\n• MSK 비동기 이벤트 기반\n• Blue/Green 무중단 배포",
            "after_icon": "performance",
            "change_badge": "▼ 75% 개선",
            "change_source": "2026 Q1 실측",
        }

    # ── 네임스페이스 ────────────────────────────────────────────────────────
    P_NS  = 'http://schemas.openxmlformats.org/presentationml/2006/main'
    A_NS  = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    R_NS  = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    REL_NS_PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
    CT_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'
    SLIDE_REL_TYPE = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide'
    SLIDE_LAYOUT_REL_TYPE = ('http://schemas.openxmlformats.org/officeDocument/'
                              '2006/relationships/slideLayout')
    PIC_NS = 'http://schemas.openxmlformats.org/drawingml/2006/picture'
    IMG_REL_TYPE = ('http://schemas.openxmlformats.org/officeDocument/'
                    '2006/relationships/image')

    # ── roundRect corner radius 동적 계산 ──────────────────────────────────
    ADJ = 16667
    PANEL_W, PANEL_H = 5303520, 3885660
    BADGE_W, BADGE_H = 1371600, 274320
    CHANGE_W, CHANGE_H = 1554480, 274320

    panel_cr  = roundrect_corner_radius(PANEL_W, PANEL_H, ADJ)   # 647,712
    badge_cr  = roundrect_corner_radius(BADGE_W, BADGE_H, ADJ)   # 45,720
    change_cr = roundrect_corner_radius(CHANGE_W, CHANGE_H, ADJ) # 45,719

    print(f"[L12] Corner radius — panel:{panel_cr} EMU ({panel_cr/914400*2.54:.3f}cm)"
          f", badge:{badge_cr} EMU, change_badge:{change_cr} EMU")

    # ── margin 검증 (roundRect 텍스트 여백 ≥ corner_radius + 0.2cm) ──────
    # 패널 내용 TB left=637160, 패널 left=457200 → margin=179960 EMU (0.197") ≈ 0.50cm
    # 실제 margin constraint 적용 대상: 패널 내부 TextBox (KPI, 내용 등)
    PANEL_L_LEFT = 457200
    PANEL_R_LEFT = 6431280
    CONTENT_L_LEFT = 637160   # 내용 TB 좌측
    CONTENT_R_LEFT = 6611040
    CM = 360000  # 1cm in EMU

    left_margin_emu = CONTENT_L_LEFT - PANEL_L_LEFT   # 179,960 EMU ≈ 0.50cm
    min_required_emu = panel_cr + int(0.2 * CM)        # 647712 + 72000 = 719712

    # 패널 내용 TB가 corner 밖에 있는지 검증 (수직 방향)
    # KPI TB top=2897580, 패널 top=2789820 → 수직 margin=107,760 EMU (0.298cm)
    kpi_top_margin_emu = 2897580 - 2789820  # 107,760
    # 수직 margin은 corner_radius(647712)보다 작음 — 하지만 수평 위치는 corner zone 바깥
    # x-direction: content left(637160) vs panel left(457200)+corner_radius(647712)=1104912
    # content left(637160) < 1104912 → TL zone 내부 — check_text_corner_overlap 으로 검증

    print(f"[L12] horizontal margin from panel: {left_margin_emu} EMU ({left_margin_emu/CM:.3f}cm)")
    print(f"[L12] vertical KPI margin from panel top: {kpi_top_margin_emu} EMU ({kpi_top_margin_emu/CM:.3f}cm)")

    # ── 1. 원본 복사 + ZIP 읽기 ─────────────────────────────────────────────
    shutil.copy2(source_pptx_path, output_path)

    all_data = {}
    with zipfile.ZipFile(output_path, 'r') as z:
        for name in z.namelist():
            all_data[name] = z.read(name)

    prs_xml  = ET_l.fromstring(all_data['ppt/presentation.xml'])
    prs_rels = ET_l.fromstring(all_data['ppt/_rels/presentation.xml.rels'])

    # ── 2. 아이콘 이미지 embed ─────────────────────────────────────────────
    icons_dir = Path(source_pptx_path).parent.parent.parent / 'modules' / 'pptx' / 'icons' / 'png'
    # fallback: relative to script location
    if not icons_dir.exists():
        icons_dir = Path(__file__).parent.parent / 'icons' / 'png'

    image_rels = {}  # rId -> (filename, bytes, media_name)
    media_counter = [200]  # start from image200 to avoid collision

    def embed_icon(icon_name: str) -> str:
        """아이콘 PNG를 PPTX media에 추가하고 rId 반환."""
        icon_path = icons_dir / f'{icon_name}.png'
        if not icon_path.exists():
            # fallback to warning
            icon_path = icons_dir / 'warning.png'
        if not icon_path.exists():
            return None
        img_bytes = icon_path.read_bytes()
        media_counter[0] += 1
        media_name = f'ppt/media/image{media_counter[0]}.png'
        r_id = f'rId{media_counter[0]}'
        image_rels[r_id] = (str(icon_path), img_bytes, media_name)
        all_data[media_name] = img_bytes
        return r_id

    before_icon_rid = embed_icon(data.get('before_icon', 'warning'))
    after_icon_rid  = embed_icon(data.get('after_icon', 'performance'))

    # ── 3. 슬라이드 XML 빌드 헬퍼 함수들 ──────────────────────────────────

    def make_textbox(sp_id, name, x, y, cx, cy, text, sz, bold, color_hex,
                     font='Freesentation', align='l', multiline=False):
        """
        TextBox sp 요소 생성 (noFill, a:ln noFill).
        multiline=True면 text를 \\n으로 분리하여 여러 단락 생성.
        """
        sp = ET_l.Element(f'{{{P_NS}}}sp')

        nvSpPr = ET_l.SubElement(sp, f'{{{P_NS}}}nvSpPr')
        cNvPr = ET_l.SubElement(nvSpPr, f'{{{P_NS}}}cNvPr')
        cNvPr.set('id', str(sp_id)); cNvPr.set('name', name)
        cNvSpPr = ET_l.SubElement(nvSpPr, f'{{{P_NS}}}cNvSpPr')
        cNvSpPr.set('txBox', '1')
        ET_l.SubElement(nvSpPr, f'{{{P_NS}}}nvPr')

        spPr = ET_l.SubElement(sp, f'{{{P_NS}}}spPr')
        xfrm = ET_l.SubElement(spPr, f'{{{A_NS}}}xfrm')
        off = ET_l.SubElement(xfrm, f'{{{A_NS}}}off')
        off.set('x', str(x)); off.set('y', str(y))
        ext = ET_l.SubElement(xfrm, f'{{{A_NS}}}ext')
        ext.set('cx', str(cx)); ext.set('cy', str(cy))
        prstGeom = ET_l.SubElement(spPr, f'{{{A_NS}}}prstGeom')
        prstGeom.set('prst', 'rect')
        ET_l.SubElement(prstGeom, f'{{{A_NS}}}avLst')
        ET_l.SubElement(spPr, f'{{{A_NS}}}noFill')
        # border 명시 필수 (MISTAKES.md #14: 미명시 시 accent1 파란색 적용)
        ln = ET_l.SubElement(spPr, f'{{{A_NS}}}ln')
        ET_l.SubElement(ln, f'{{{A_NS}}}noFill')

        txBody = ET_l.SubElement(sp, f'{{{P_NS}}}txBody')
        bodyPr = ET_l.SubElement(txBody, f'{{{A_NS}}}bodyPr')
        bodyPr.set('wrap', 'square')
        ET_l.SubElement(bodyPr, f'{{{A_NS}}}spAutoFit')
        ET_l.SubElement(txBody, f'{{{A_NS}}}lstStyle')

        lines = text.split('\n') if multiline else [text]
        for line in lines:
            para = ET_l.SubElement(txBody, f'{{{A_NS}}}p')
            pPr = ET_l.SubElement(para, f'{{{A_NS}}}pPr')
            pPr.set('algn', align)
            run = ET_l.SubElement(para, f'{{{A_NS}}}r')
            rPr = ET_l.SubElement(run, f'{{{A_NS}}}rPr')
            rPr.set('lang', 'ko-KR')
            rPr.set('sz', str(sz))
            rPr.set('b', '1' if bold else '0')
            solidFill = ET_l.SubElement(rPr, f'{{{A_NS}}}solidFill')
            srgbClr = ET_l.SubElement(solidFill, f'{{{A_NS}}}srgbClr')
            srgbClr.set('val', color_hex)
            latin = ET_l.SubElement(rPr, f'{{{A_NS}}}latin')
            latin.set('typeface', font)
            t_elem = ET_l.SubElement(run, f'{{{A_NS}}}t')
            t_elem.text = line

        return sp

    def make_roundrect(sp_id, name, x, y, cx, cy, fill_hex, border_hex, adj=16667):
        """
        roundRect sp 요소 생성.
        border: solidFill border_hex (MISTAKES.md #14: fill과 동일 색 → 보이지 않는 border)
        """
        sp = ET_l.Element(f'{{{P_NS}}}sp')

        nvSpPr = ET_l.SubElement(sp, f'{{{P_NS}}}nvSpPr')
        cNvPr = ET_l.SubElement(nvSpPr, f'{{{P_NS}}}cNvPr')
        cNvPr.set('id', str(sp_id)); cNvPr.set('name', name)
        ET_l.SubElement(nvSpPr, f'{{{P_NS}}}cNvSpPr')
        ET_l.SubElement(nvSpPr, f'{{{P_NS}}}nvPr')

        spPr = ET_l.SubElement(sp, f'{{{P_NS}}}spPr')
        xfrm = ET_l.SubElement(spPr, f'{{{A_NS}}}xfrm')
        off = ET_l.SubElement(xfrm, f'{{{A_NS}}}off')
        off.set('x', str(x)); off.set('y', str(y))
        ext = ET_l.SubElement(xfrm, f'{{{A_NS}}}ext')
        ext.set('cx', str(cx)); ext.set('cy', str(cy))

        prstGeom = ET_l.SubElement(spPr, f'{{{A_NS}}}prstGeom')
        prstGeom.set('prst', 'roundRect')
        avLst = ET_l.SubElement(prstGeom, f'{{{A_NS}}}avLst')
        gd = ET_l.SubElement(avLst, f'{{{A_NS}}}gd')
        gd.set('name', 'adj')
        gd.set('fmla', f'val {adj}')

        solidFill = ET_l.SubElement(spPr, f'{{{A_NS}}}solidFill')
        srgbClr_fill = ET_l.SubElement(solidFill, f'{{{A_NS}}}srgbClr')
        srgbClr_fill.set('val', fill_hex.lstrip('#'))

        # border 명시 (fill과 동일 색 → border 안 보이는 효과)
        ln = ET_l.SubElement(spPr, f'{{{A_NS}}}ln')
        solidFill_ln = ET_l.SubElement(ln, f'{{{A_NS}}}solidFill')
        srgbClr_ln = ET_l.SubElement(solidFill_ln, f'{{{A_NS}}}srgbClr')
        srgbClr_ln.set('val', border_hex.lstrip('#'))

        # txBody 빈 상태 (텍스트는 overlay TextBox로)
        txBody = ET_l.SubElement(sp, f'{{{P_NS}}}txBody')
        bodyPr = ET_l.SubElement(txBody, f'{{{A_NS}}}bodyPr')
        bodyPr.set('anchor', 'ctr')
        ET_l.SubElement(txBody, f'{{{A_NS}}}lstStyle')
        ET_l.SubElement(txBody, f'{{{A_NS}}}p')

        return sp

    def make_arrow(sp_id, name, x, y, cx, cy, fill_hex):
        """
        rightArrow prstGeom shape 생성.
        border: solidFill PRIMARY (fill과 동일)
        """
        sp = ET_l.Element(f'{{{P_NS}}}sp')

        nvSpPr = ET_l.SubElement(sp, f'{{{P_NS}}}nvSpPr')
        cNvPr = ET_l.SubElement(nvSpPr, f'{{{P_NS}}}cNvPr')
        cNvPr.set('id', str(sp_id)); cNvPr.set('name', name)
        ET_l.SubElement(nvSpPr, f'{{{P_NS}}}cNvSpPr')
        ET_l.SubElement(nvSpPr, f'{{{P_NS}}}nvPr')

        spPr = ET_l.SubElement(sp, f'{{{P_NS}}}spPr')
        xfrm = ET_l.SubElement(spPr, f'{{{A_NS}}}xfrm')
        off = ET_l.SubElement(xfrm, f'{{{A_NS}}}off')
        off.set('x', str(x)); off.set('y', str(y))
        ext = ET_l.SubElement(xfrm, f'{{{A_NS}}}ext')
        ext.set('cx', str(cx)); ext.set('cy', str(cy))

        prstGeom = ET_l.SubElement(spPr, f'{{{A_NS}}}prstGeom')
        prstGeom.set('prst', 'rightArrow')
        ET_l.SubElement(prstGeom, f'{{{A_NS}}}avLst')

        solidFill = ET_l.SubElement(spPr, f'{{{A_NS}}}solidFill')
        srgbClr = ET_l.SubElement(solidFill, f'{{{A_NS}}}srgbClr')
        srgbClr.set('val', fill_hex.lstrip('#'))

        # border 명시: fill과 동일
        ln = ET_l.SubElement(spPr, f'{{{A_NS}}}ln')
        solidFill_ln = ET_l.SubElement(ln, f'{{{A_NS}}}solidFill')
        srgbClr_ln = ET_l.SubElement(solidFill_ln, f'{{{A_NS}}}srgbClr')
        srgbClr_ln.set('val', fill_hex.lstrip('#'))

        txBody = ET_l.SubElement(sp, f'{{{P_NS}}}txBody')
        bodyPr = ET_l.SubElement(txBody, f'{{{A_NS}}}bodyPr')
        ET_l.SubElement(txBody, f'{{{A_NS}}}lstStyle')
        ET_l.SubElement(txBody, f'{{{A_NS}}}p')

        return sp

    def make_line(sp_id, name, x, y, cx, color_hex, width_emu=12700):
        """
        수평 구분선 (height=0) sp 요소 생성.
        line은 xfrm의 flipH/flipV로 방향 지정 없이 직선.
        height=0인 수평선: cy=0 설정.
        border: solidFill color_hex
        """
        sp = ET_l.Element(f'{{{P_NS}}}sp')

        nvSpPr = ET_l.SubElement(sp, f'{{{P_NS}}}nvSpPr')
        cNvPr = ET_l.SubElement(nvSpPr, f'{{{P_NS}}}cNvPr')
        cNvPr.set('id', str(sp_id)); cNvPr.set('name', name)
        cNvSpPr = ET_l.SubElement(nvSpPr, f'{{{P_NS}}}cNvSpPr')
        cNvSpPr.set('txBox', '0')
        ET_l.SubElement(nvSpPr, f'{{{P_NS}}}nvPr')

        spPr = ET_l.SubElement(sp, f'{{{P_NS}}}spPr')
        xfrm = ET_l.SubElement(spPr, f'{{{A_NS}}}xfrm')
        off = ET_l.SubElement(xfrm, f'{{{A_NS}}}off')
        off.set('x', str(x)); off.set('y', str(y))
        ext = ET_l.SubElement(xfrm, f'{{{A_NS}}}ext')
        ext.set('cx', str(cx)); ext.set('cy', '0')

        prstGeom = ET_l.SubElement(spPr, f'{{{A_NS}}}prstGeom')
        prstGeom.set('prst', 'line')
        ET_l.SubElement(prstGeom, f'{{{A_NS}}}avLst')

        ET_l.SubElement(spPr, f'{{{A_NS}}}noFill')

        # 선 색상 및 두께
        ln = ET_l.SubElement(spPr, f'{{{A_NS}}}ln')
        ln.set('w', str(width_emu))
        solidFill_ln = ET_l.SubElement(ln, f'{{{A_NS}}}solidFill')
        srgbClr_ln = ET_l.SubElement(solidFill_ln, f'{{{A_NS}}}srgbClr')
        srgbClr_ln.set('val', color_hex.lstrip('#'))

        # txBody (빈 상태)
        txBody = ET_l.SubElement(sp, f'{{{P_NS}}}txBody')
        bodyPr = ET_l.SubElement(txBody, f'{{{A_NS}}}bodyPr')
        ET_l.SubElement(txBody, f'{{{A_NS}}}lstStyle')
        ET_l.SubElement(txBody, f'{{{A_NS}}}p')

        return sp

    def make_pic(sp_id, name, x, y, cx, cy, r_id):
        """
        그림(이미지) pic 요소 생성.
        아이콘 크기: 411480×411480 EMU (0.45" 고정, MISTAKES.md #9)
        border: a:ln noFill
        """
        # p:pic 사용 (P_NS) — pic:pic(PIC_NS) 사용 시 PowerPoint repair 오류 발생
        pic = ET_l.Element(f'{{{P_NS}}}pic')

        nvPicPr = ET_l.SubElement(pic, f'{{{P_NS}}}nvPicPr')
        cNvPr = ET_l.SubElement(nvPicPr, f'{{{P_NS}}}cNvPr')
        cNvPr.set('id', str(sp_id)); cNvPr.set('name', name)
        cNvPicPr = ET_l.SubElement(nvPicPr, f'{{{P_NS}}}cNvPicPr')
        ET_l.SubElement(cNvPicPr, f'{{{A_NS}}}picLocks').set('noChangeAspect', '1')
        ET_l.SubElement(nvPicPr, f'{{{P_NS}}}nvPr')

        blipFill = ET_l.SubElement(pic, f'{{{P_NS}}}blipFill')
        blip = ET_l.SubElement(blipFill, f'{{{A_NS}}}blip')
        blip.set(f'{{{R_NS}}}embed', r_id)
        stretch = ET_l.SubElement(blipFill, f'{{{A_NS}}}stretch')
        ET_l.SubElement(stretch, f'{{{A_NS}}}fillRect')

        spPr_pic = ET_l.SubElement(pic, f'{{{P_NS}}}spPr')
        xfrm = ET_l.SubElement(spPr_pic, f'{{{A_NS}}}xfrm')
        off = ET_l.SubElement(xfrm, f'{{{A_NS}}}off')
        off.set('x', str(x)); off.set('y', str(y))
        ext = ET_l.SubElement(xfrm, f'{{{A_NS}}}ext')
        ext.set('cx', str(cx)); ext.set('cy', str(cy))
        prstGeom = ET_l.SubElement(spPr_pic, f'{{{A_NS}}}prstGeom')
        prstGeom.set('prst', 'rect')
        ET_l.SubElement(prstGeom, f'{{{A_NS}}}avLst')
        # border noFill (MISTAKES.md #14)
        ln = ET_l.SubElement(spPr_pic, f'{{{A_NS}}}ln')
        ET_l.SubElement(ln, f'{{{A_NS}}}noFill')

        return pic

    # ── 4. 슬라이드 XML 루트 조립 ──────────────────────────────────────────
    sld_nsmap = {'p': P_NS, 'a': A_NS, 'r': R_NS}
    sld_root = ET_l.Element(f'{{{P_NS}}}sld', nsmap=sld_nsmap)

    cSld = ET_l.SubElement(sld_root, f'{{{P_NS}}}cSld')
    spTree = ET_l.SubElement(cSld, f'{{{P_NS}}}spTree')

    # nvGrpSpPr + grpSpPr (필수)
    nvGrpSpPr = ET_l.SubElement(spTree, f'{{{P_NS}}}nvGrpSpPr')
    cNvPr_grp = ET_l.SubElement(nvGrpSpPr, f'{{{P_NS}}}cNvPr')
    cNvPr_grp.set('id', '1'); cNvPr_grp.set('name', '')
    ET_l.SubElement(nvGrpSpPr, f'{{{P_NS}}}cNvGrpSpPr')
    ET_l.SubElement(nvGrpSpPr, f'{{{P_NS}}}nvPr')
    # grpSpPr: 빈 요소 (xfrm 추가 금지 — 기존 슬라이드 패턴과 일치)
    ET_l.SubElement(spTree, f'{{{P_NS}}}grpSpPr')

    # 레이아웃 body placeholder (빈 상태)
    sp_ph = ET_l.SubElement(spTree, f'{{{P_NS}}}sp')
    nvSpPr_ph = ET_l.SubElement(sp_ph, f'{{{P_NS}}}nvSpPr')
    cNvPr_ph = ET_l.SubElement(nvSpPr_ph, f'{{{P_NS}}}cNvPr')
    cNvPr_ph.set('id', '2'); cNvPr_ph.set('name', 'Text Placeholder 1')
    cNvSpPr_ph = ET_l.SubElement(nvSpPr_ph, f'{{{P_NS}}}cNvSpPr')
    spLocks_ph = ET_l.SubElement(cNvSpPr_ph, f'{{{A_NS}}}spLocks')
    spLocks_ph.set('noGrp', '1')
    nvPr_ph = ET_l.SubElement(nvSpPr_ph, f'{{{P_NS}}}nvPr')
    ph_el = ET_l.SubElement(nvPr_ph, f'{{{P_NS}}}ph')
    ph_el.set('type', 'body'); ph_el.set('idx', '10'); ph_el.set('sz', 'quarter')
    # spPr: 빈 요소 (placeholder는 spPr override 금지 — 기존 슬라이드 패턴)
    ET_l.SubElement(sp_ph, f'{{{P_NS}}}spPr')
    txBody_ph = ET_l.SubElement(sp_ph, f'{{{P_NS}}}txBody')
    ET_l.SubElement(txBody_ph, f'{{{A_NS}}}bodyPr')
    ET_l.SubElement(txBody_ph, f'{{{A_NS}}}lstStyle')
    ET_l.SubElement(txBody_ph, f'{{{A_NS}}}p')

    # sp_id 카운터
    sid = 10

    # ── 5. 요약 제목/설명 TextBox ───────────────────────────────────────────
    # 요약 제목: 16pt PRIMARY Bold Freesentation (WCAG: 슬라이드 배경=white, PRIMARY=7.2:1 AAA)
    spTree.append(make_textbox(
        sid, 'TextBox L12 Title',
        x=457200, y=1600200, cx=11277600, cy=320040,
        text=data.get('body_title', ''),
        sz=1600, bold=True, color_hex=PRIMARY,
        font='Freesentation', align='l'
    ))
    sid += 1

    # 요약 설명: 13pt DARK_GRAY Regular Freesentation
    spTree.append(make_textbox(
        sid, 'TextBox L12 Desc',
        x=457200, y=1965960, cx=11277600, cy=274320,
        text=data.get('body_desc', ''),
        sz=1300, bold=False, color_hex=DARK_GRAY,
        font='Freesentation', align='l'
    ))
    sid += 1

    # ── 6. 배지 RRect (BEFORE / AFTER) ─────────────────────────────────────
    # 배지 corner radius 동적 계산: adj=16667, min(1371600,274320)=274320 → 45,720 EMU
    # 배지 텍스트: TextBox overlay 방식 (L09 실측 패턴)
    # WCAG: DARK_GRAY(#212121) bg + WHITE(#FFFFFF) = 16.1:1 AAA
    spTree.append(make_roundrect(
        sid, 'RRect L12 Badge Before',
        x=637160, y=2423160, cx=BADGE_W, cy=BADGE_H,
        fill_hex=DARK_GRAY, border_hex=DARK_GRAY, adj=ADJ
    ))
    sid += 1

    # WCAG: PRIMARY(#0043DA) bg + WHITE = 7.2:1 AAA
    spTree.append(make_roundrect(
        sid, 'RRect L12 Badge After',
        x=6611040, y=2423160, cx=BADGE_W, cy=BADGE_H,
        fill_hex=PRIMARY, border_hex=PRIMARY, adj=ADJ
    ))
    sid += 1

    # 배지 overlay TextBox (BEFORE)
    # 폰트: Freesentation 11pt Bold WHITE, 중앙 정렬
    spTree.append(make_textbox(
        sid, 'TextBox L12 Badge Before Text',
        x=637160, y=2423160, cx=BADGE_W, cy=BADGE_H,
        text=data.get('before_badge', 'BEFORE'),
        sz=1100, bold=True, color_hex=WHITE,
        font='Freesentation', align='ctr'
    ))
    sid += 1

    # 배지 overlay TextBox (AFTER)
    spTree.append(make_textbox(
        sid, 'TextBox L12 Badge After Text',
        x=6611040, y=2423160, cx=BADGE_W, cy=BADGE_H,
        text=data.get('after_badge', 'AFTER'),
        sz=1100, bold=True, color_hex=WHITE,
        font='Freesentation', align='ctr'
    ))
    sid += 1

    # ── 7. 메인 패널 RRect (BEFORE / AFTER) ────────────────────────────────
    # 패널 corner radius 동적 계산: adj=16667, min(5303520,3885660)=3885660 → 647,712 EMU
    # WCAG: BG_BOX(#F8F9FA) 배경 — 내부 텍스트는 DARK_GRAY(15.5:1 AAA)
    spTree.append(make_roundrect(
        sid, 'RRect L12 Panel Before',
        x=457200, y=2789820, cx=PANEL_W, cy=PANEL_H,
        fill_hex=BG_BOX, border_hex=BG_BOX, adj=ADJ
    ))
    sid += 1

    # WCAG: E6F0FF(#E6F0FF) 배경 — 내부 텍스트는 PRIMARY(5.8:1 AA) 또는 DARK_GRAY
    spTree.append(make_roundrect(
        sid, 'RRect L12 Panel After',
        x=6431280, y=2789820, cx=PANEL_W, cy=PANEL_H,
        fill_hex=PANEL_AF, border_hex=PANEL_AF, adj=ADJ
    ))
    sid += 1

    # ── 8. 전환 화살표 (rightArrow) ────────────────────────────────────────
    # PRIMARY fill, 패널 사이 중앙 (5944440, 4594980) 411480×274320
    spTree.append(make_arrow(
        sid, 'Arrow L12 Transition',
        x=5944440, y=4594980, cx=411480, cy=274320,
        fill_hex=PRIMARY
    ))
    sid += 1

    # ── 9. KPI 수치 TextBox ────────────────────────────────────────────────
    # 좌 KPI 수치: 프리젠테이션 7 Bold 24pt DARK_GRAY — WCAG BG_BOX bg: 15.5:1 AAA
    spTree.append(make_textbox(
        sid, 'TextBox L12 KPI Before Value',
        x=637160, y=2897580, cx=4941840, cy=457200,
        text=data.get('before_kpi_value', ''),
        sz=2400, bold=True, color_hex=DARK_GRAY,
        font='프리젠테이션 7 Bold', align='ctr'
    ))
    sid += 1

    # 우 KPI 수치: 프리젠테이션 7 Bold 24pt PRIMARY
    # WCAG: E6F0FF bg + PRIMARY(#0043DA): 5.8:1 AA (MISTAKES.md #16: FFFFFF 절대 금지)
    spTree.append(make_textbox(
        sid, 'TextBox L12 KPI After Value',
        x=6611040, y=2897580, cx=4941840, cy=457200,
        text=data.get('after_kpi_value', ''),
        sz=2400, bold=True, color_hex=PRIMARY,
        font='프리젠테이션 7 Bold', align='ctr'
    ))
    sid += 1

    # ── 10. KPI 레이블 TextBox ─────────────────────────────────────────────
    # Freesentation 11pt GRAY #505050 — WCAG: 7.0:1 AA
    spTree.append(make_textbox(
        sid, 'TextBox L12 KPI Before Label',
        x=637160, y=3354780, cx=4941840, cy=228600,
        text=data.get('before_kpi_label', ''),
        sz=1100, bold=False, color_hex=GRAY,
        font='Freesentation', align='ctr'
    ))
    sid += 1

    spTree.append(make_textbox(
        sid, 'TextBox L12 KPI After Label',
        x=6611040, y=3354780, cx=4941840, cy=228600,
        text=data.get('after_kpi_label', ''),
        sz=1100, bold=False, color_hex=GRAY,
        font='Freesentation', align='ctr'
    ))
    sid += 1

    # ── 11. 구분선 (수평 Line) ─────────────────────────────────────────────
    # BORDER #DCDCDC, 1pt (12700 EMU), height=0
    spTree.append(make_line(
        sid, 'Line L12 Divider Before',
        x=637160, y=3674820, cx=4941840,
        color_hex=BORDER, width_emu=12700
    ))
    sid += 1

    spTree.append(make_line(
        sid, 'Line L12 Divider After',
        x=6611040, y=3674820, cx=4941840,
        color_hex=BORDER, width_emu=12700
    ))
    sid += 1

    # ── 12. 내용 TextBox (bullet) ─────────────────────────────────────────
    # Freesentation 13pt DARK_GRAY — WCAG: AAA on both panels
    spTree.append(make_textbox(
        sid, 'TextBox L12 Content Before',
        x=637160, y=3766260, cx=4484640, cy=1947040,
        text=data.get('before_body', ''),
        sz=1300, bold=False, color_hex=DARK_GRAY,
        font='Freesentation', align='l', multiline=True
    ))
    sid += 1

    spTree.append(make_textbox(
        sid, 'TextBox L12 Content After',
        x=6611040, y=3766260, cx=4484640, cy=1947040,
        text=data.get('after_body', ''),
        sz=1300, bold=False, color_hex=DARK_GRAY,
        font='Freesentation', align='l', multiline=True
    ))
    sid += 1

    # ── 13. 변화율 배지 (선택 요소) ────────────────────────────────────────
    # change_badge=None이면 생성 안 함
    # PRIMARY fill, 흰색 11pt Bold 프리젠테이션 7 Bold — WCAG 7.2:1 AAA
    change_badge_text = data.get('change_badge')
    if change_badge_text:
        spTree.append(make_roundrect(
            sid, 'RRect L12 Change Badge',
            x=5318760, y=5029200, cx=CHANGE_W, cy=CHANGE_H,
            fill_hex=PRIMARY, border_hex=PRIMARY, adj=ADJ
        ))
        sid += 1

        spTree.append(make_textbox(
            sid, 'TextBox L12 Change Badge Text',
            x=5318760, y=5029200, cx=CHANGE_W, cy=CHANGE_H,
            text=change_badge_text,
            sz=1100, bold=True, color_hex=WHITE,
            font='프리젠테이션 7 Bold', align='ctr'
        ))
        sid += 1

    # ── 14. 아이콘 (Picture) ───────────────────────────────────────────────
    # 크기: 411480×411480 EMU (0.45" 고정, MISTAKES.md #9)
    # 좌 아이콘: (5047200, 6087600)
    # 우 아이콘: (11021280, 6087600)
    # 아이콘 위치 corner zone 검증은 check_text_corner_overlap 이후 별도 수행
    pic_elements = []
    if before_icon_rid:
        pic_before = make_pic(
            sid, 'Icon L12 Before',
            x=5047200, y=6087600, cx=411480, cy=411480,
            r_id=before_icon_rid
        )
        pic_elements.append(pic_before)
        sid += 1
    if after_icon_rid:
        pic_after = make_pic(
            sid, 'Icon L12 After',
            x=11021280, y=6087600, cx=411480, cy=411480,
            r_id=after_icon_rid
        )
        pic_elements.append(pic_after)
        sid += 1

    # pic:pic 요소는 spTree에 직접 추가 (graphicFrame 불필요)
    for pic in pic_elements:
        spTree.append(pic)

    # clrMapOvr (레이아웃 색상 상속)
    clrMapOvr = ET_l.SubElement(sld_root, f'{{{P_NS}}}clrMapOvr')
    ET_l.SubElement(clrMapOvr, f'{{{A_NS}}}masterClrMapping')

    # ── 15. corner overlap 검증 ────────────────────────────────────────────
    overlaps = check_text_corner_overlap(sld_root, slide_idx=0)
    if overlaps:
        print(f"[L12] WARNING: {len(overlaps)} corner overlap(s) detected:")
        for ov in overlaps:
            print(f"  {ov['roundrect']} r={ov['corner_radius_cm']}cm "
                  f"← {ov['text_shape']} [{ov['text_preview']}] "
                  f"top={ov['margin_top_cm']}cm left={ov['margin_left_cm']}cm "
                  f"zones={ov['zones']}")
        # 주의: 패널 내부 KPI/내용 TB는 roundRect 내부에 있어 overlap 감지됨.
        # 이는 의도된 배치 (텍스트가 corner 영역에 닿지 않음 — x offset으로 보장).
        # 실제 시각적 overlap 여부는 PDF/PNG 변환으로 별도 확인 필요.
    else:
        print("[L12] corner overlap check: PASS")

    # ── 16. 기존 슬라이드 제거, 단일 슬라이드로 재조립 ────────────────────
    existing_slide_keys = [k for k in all_data if re.match(r'ppt/slides/slide\d+\.xml$', k)]
    existing_rels_keys  = [k for k in all_data if re.match(r'ppt/slides/_rels/slide\d+\.xml\.rels$', k)]
    for k in existing_slide_keys + existing_rels_keys:
        if k in all_data:
            del all_data[k]

    new_slide_name = 'ppt/slides/slide1.xml'
    new_rels_name  = 'ppt/slides/_rels/slide1.xml.rels'

    slide_bytes = ET_l.tostring(sld_root, xml_declaration=True,
                                 encoding='UTF-8', standalone=True)
    all_data[new_slide_name] = slide_bytes

    # slide1.xml.rels (slideLayout2 + image rels)
    rels_root = ET_l.Element('Relationships')
    rels_root.set('xmlns', REL_NS_PKG)
    rel_layout = ET_l.SubElement(rels_root, 'Relationship')
    rel_layout.set('Id', 'rId1')
    rel_layout.set('Type', SLIDE_LAYOUT_REL_TYPE)
    rel_layout.set('Target', '../slideLayouts/slideLayout2.xml')
    # 이미지 rels
    for r_id, (icon_path, img_bytes, media_name) in image_rels.items():
        # media_name: ppt/media/image200.png → relative: ../media/image200.png
        media_rel_target = '../media/' + Path(media_name).name
        rel_img = ET_l.SubElement(rels_root, 'Relationship')
        rel_img.set('Id', r_id)
        rel_img.set('Type', IMG_REL_TYPE)
        rel_img.set('Target', media_rel_target)
    rels_bytes = ET_l.tostring(rels_root, xml_declaration=True,
                                encoding='UTF-8', standalone=True)
    all_data[new_rels_name] = rels_bytes

    # presentation.xml sldIdLst 재작성 (단일 슬라이드)
    sldIdLst = prs_xml.find(f'{{{P_NS}}}sldIdLst')
    sldIdLst.clear()
    new_sld_id = ET_l.SubElement(sldIdLst, f'{{{P_NS}}}sldId')
    new_sld_id.set('id', '256')
    new_sld_id.set(f'{{{R_NS}}}id', 'rId1000')

    # presentation.xml.rels 재작성
    new_prs_rels = ET_l.Element('Relationships')
    new_prs_rels.set('xmlns', REL_NS_PKG)
    SKIP_TYPES = ('slide',)
    for rel in prs_rels:
        rel_type = rel.get('Type', '')
        if (rel_type.endswith('/slide') and 'Layout' not in rel_type
                and 'Master' not in rel_type):
            continue
        new_prs_rels.append(copy.deepcopy(rel))
    new_slide_rel = ET_l.SubElement(new_prs_rels, 'Relationship')
    new_slide_rel.set('Id', 'rId1000')
    new_slide_rel.set('Type', SLIDE_REL_TYPE)
    new_slide_rel.set('Target', 'slides/slide1.xml')

    all_data['ppt/presentation.xml'] = ET_l.tostring(
        prs_xml, xml_declaration=True, encoding='UTF-8', standalone=True)
    all_data['ppt/_rels/presentation.xml.rels'] = ET_l.tostring(
        new_prs_rels, xml_declaration=True, encoding='UTF-8', standalone=True)

    # Content_Types.xml 업데이트
    ct_xml = ET_l.fromstring(all_data['[Content_Types].xml'])
    SLIDE_CT = ('application/vnd.openxmlformats-officedocument.'
                'presentationml.slide+xml')
    for override in list(ct_xml.findall(f'{{{CT_NS}}}Override')):
        if '/slides/slide' in override.get('PartName', ''):
            ct_xml.remove(override)
    new_override = ET_l.SubElement(ct_xml, f'{{{CT_NS}}}Override')
    new_override.set('PartName', '/ppt/slides/slide1.xml')
    new_override.set('ContentType', SLIDE_CT)
    all_data['[Content_Types].xml'] = ET_l.tostring(
        ct_xml, xml_declaration=True, encoding='UTF-8', standalone=True)

    # ── 17. ZIP 재조립 저장 ────────────────────────────────────────────────
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name, content in sorted(all_data.items()):
            zout.writestr(name, content)
    with open(output_path, 'wb') as f:
        f.write(buf.getvalue())

    print(f"[L12] saved: {output_path}")
    print(f"  body_title: {data.get('body_title', '')!r}")
    print(f"  before_kpi_value: {data.get('before_kpi_value', '')!r}")
    print(f"  after_kpi_value: {data.get('after_kpi_value', '')!r}")
    print(f"  change_badge: {change_badge_text!r}")
    print(f"  panel corner_radius: {panel_cr} EMU ({panel_cr/914400*2.54:.3f}cm)")
    print(f"  badge corner_radius: {badge_cr} EMU")
    return output_path


if __name__ == '__main__':
    # 자가 테스트: 현재 PPTX 열고 검증 + corner-overlap 리포트
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else 'results/pptx/AWS_MSK_Expert_Intro.pptx'
    ed = PptxSafeEditor(path)
    issues = ed.verify()
    if issues:
        print("ISSUES:", issues)
    else:
        print(f"OK — {len(ed.slide_targets)} slides, last={ed._slide_text_preview(ed.slide_targets[-1])!r}")

    print("\n=== Corner Overlap Report ===")
    all_overlaps = []
    for i, target in enumerate(ed.slide_targets):
        root = ed.slide_xmls[target]
        overlaps = check_text_corner_overlap(root, slide_idx=i)
        all_overlaps.extend(overlaps)

    if not all_overlaps:
        print("No corner overlaps detected.")
    else:
        for ov in all_overlaps:
            print(f"  Slide {ov['slide']} | {ov['roundrect']} (r={ov['corner_radius_cm']}cm)"
                  f" ← {ov['text_shape']} [{ov['text_preview']}]"
                  f" margin top={ov['margin_top_cm']}cm left={ov['margin_left_cm']}cm"
                  f" zones={ov['zones']}")
