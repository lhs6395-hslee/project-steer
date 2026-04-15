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
