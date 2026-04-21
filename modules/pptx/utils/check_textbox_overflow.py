"""
check_textbox_overflow.py — Universal textbox overflow detector & fixer
Usage:
  python check_textbox_overflow.py <file.pptx> [--fix] [--slide N]

Used by Option 1 / 2 / 3 post-generation verification.
"""

import argparse
import sys
import zipfile
import copy
import lxml.etree as ET
from pathlib import Path

# ── Namespaces ────────────────────────────────────────────────────────────────
NSM = {
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}
SLIDE_W  = 12_192_000   # 13.333" in EMU
SLIDE_H  = 6_858_000    # 7.500" in EMU
PT_TO_EMU = 12_700       # 1pt = 12,700 EMU
LINE_SPACING = 1.15      # default line-height multiplier

# ── Per-character EM widths ───────────────────────────────────────────────────
def _char_em(ch: str) -> float:
    """Return EM width of a single character."""
    cp = ord(ch)
    # CJK unified ideographs, Hangul syllables / jamo, fullwidth
    if (0xAC00 <= cp <= 0xD7A3 or   # Hangul syllables
        0x1100 <= cp <= 0x11FF or   # Hangul Jamo
        0x4E00 <= cp <= 0x9FFF or   # CJK unified
        0xFF00 <= cp <= 0xFFEF):    # Fullwidth forms
        return 1.0
    if ch == ' ':
        return 0.28
    # ASCII printable
    if 0x21 <= cp <= 0x7E:
        return 0.60
    # fallback (arrows, symbols, etc.)
    return 0.85


def char_width_emu(ch: str, font_size_pt: float) -> int:
    """Return EMU width of one character at given font size."""
    return int(_char_em(ch) * font_size_pt * PT_TO_EMU)


def text_width_emu(text: str, font_size_pt: float) -> int:
    """Return total EMU width of text rendered on one line."""
    return sum(char_width_emu(c, font_size_pt) for c in text)


def count_lines(text: str, font_size_pt: float, box_width_emu: int) -> int:
    """
    Simulate word-wrap and return number of visual lines.
    Splits on spaces; wraps when a word would exceed box_width_emu.
    """
    words = text.split(' ')
    lines = 0
    line_w = 0
    space_w = char_width_emu(' ', font_size_pt)

    for word in words:
        w = text_width_emu(word, font_size_pt)
        if line_w == 0:
            line_w = w
        elif line_w + space_w + w <= box_width_emu:
            line_w += space_w + w
        else:
            lines += 1
            line_w = w

    lines += 1  # last line
    return lines


def line_height_emu(font_size_pt: float) -> int:
    return int(font_size_pt * PT_TO_EMU * LINE_SPACING)


def required_height_emu(text: str, font_size_pt: float, box_width_emu: int) -> int:
    n = count_lines(text, font_size_pt, box_width_emu)
    return int(n * line_height_emu(font_size_pt) * 1.1)  # +10% padding


# ── PPTX reader helpers ───────────────────────────────────────────────────────

def _get_xfrm(sp):
    return sp.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}xfrm')


def _shapes(slide_xml: bytes):
    root = ET.fromstring(slide_xml)
    return root.findall('.//p:sp', NSM), root


def _sp_info(sp):
    nvpr = sp.find('.//p:nvSpPr/p:cNvPr', NSM)
    name = nvpr.get('name', '') if nvpr is not None else '?'
    xfrm = _get_xfrm(sp)
    if xfrm is None:
        return name, None, None, None, None
    off = xfrm.find('{http://schemas.openxmlformats.org/drawingml/2006/main}off')
    ext = xfrm.find('{http://schemas.openxmlformats.org/drawingml/2006/main}ext')
    x  = int(off.get('x', 0))
    y  = int(off.get('y', 0))
    cx = int(ext.get('cx', 0))
    cy = int(ext.get('cy', 0))
    return name, x, y, cx, cy


def _sp_text_and_font(sp):
    """Return (full_text, font_size_pt). Font size from first rPr found."""
    texts = [r.text or '' for r in sp.findall('.//a:t', NSM)]
    full = ' '.join(t for t in texts if t.strip())
    rpr = sp.find('.//a:r/a:rPr', NSM)
    sz_str = rpr.get('sz') if rpr is not None else None
    font_pt = int(sz_str) / 100.0 if sz_str else 18.0
    return full, font_pt


# ── Overflow check ────────────────────────────────────────────────────────────

def check_slide(slide_xml: bytes, slide_path: str):
    """
    Returns list of dicts:
      {name, x, y, cx, cy, text, font_pt, n_lines, req_height, overflow}
    """
    shapes, _ = _shapes(slide_xml)
    issues = []
    for sp in shapes:
        name, x, y, cx, cy = _sp_info(sp)
        if cx is None:
            continue
        text, font_pt = _sp_text_and_font(sp)
        if not text:
            continue
        n = count_lines(text, font_pt, cx)
        req_h = required_height_emu(text, font_pt, cx)
        if req_h > cy:
            issues.append({
                'name': name, 'x': x, 'y': y, 'cx': cx, 'cy': cy,
                'text': text, 'font_pt': font_pt,
                'n_lines': n, 'req_height': req_h,
                'overflow': True,
            })
    return issues


# ── Auto-fix ─────────────────────────────────────────────────────────────────

def _set_xfrm(sp, x, y, cx, cy):
    xfrm = _get_xfrm(sp)
    A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    xfrm.find(f'{{{A}}}off').set('x', str(x))
    xfrm.find(f'{{{A}}}off').set('y', str(y))
    xfrm.find(f'{{{A}}}ext').set('cx', str(cx))
    xfrm.find(f'{{{A}}}ext').set('cy', str(cy))


def _find_min_cx(text: str, font_pt: float, cy: int, max_cx: int) -> int:
    """
    Binary-search for the minimum cx (in EMU) such that
    required_height_emu(text, font_pt, cx) <= cy.
    Falls back to max_cx if text cannot fit even at max width.
    """
    lo, hi = int(font_pt * PT_TO_EMU), max_cx
    if required_height_emu(text, font_pt, hi) > cy:
        return hi  # can't fit — caller will extend cy
    while hi - lo > 9_144:   # ~0.01" precision
        mid = (lo + hi) // 2
        if required_height_emu(text, font_pt, mid) <= cy:
            hi = mid
        else:
            lo = mid
    return hi


def fix_overflow(slide_xml: bytes, margin_emu: int = 457_200) -> tuple[bytes, list[str]]:
    """
    Auto-fix overflowing textboxes.
    Strategy (per overflowing shape):
      1. Find minimum cx so text height fits within cy (binary search).
      2. Center the box horizontally: x = (SLIDE_W - min_cx) / 2.
         → Left margin = right margin (user requirement for cover textboxes).
      3. If text still doesn't fit at max_cx, extend cy downward.
      4. Shift any linked subtitle box (smaller font, just below title) to avoid overlap,
         applying the same x/cx alignment.
    Returns (patched_xml_bytes, list_of_fix_messages).
    """
    shapes, root = _shapes(slide_xml)
    fixes = []

    sp_map = {}
    for sp in shapes:
        nvpr = sp.find('.//p:nvSpPr/p:cNvPr', NSM)
        if nvpr is not None:
            sp_map[nvpr.get('name', '')] = sp

    max_cx = SLIDE_W - 2 * margin_emu   # 11,277,600

    # Track which shapes have already been repositioned (to avoid double-processing)
    already_fixed: set[str] = set()

    for sp in list(sp_map.values()):
        name, x, y, cx, cy = _sp_info(sp)
        if cx is None or name in already_fixed:
            continue
        text, font_pt = _sp_text_and_font(sp)
        if not text:
            continue

        req_h = required_height_emu(text, font_pt, cx)
        if req_h <= cy:
            continue

        # Step 1: find minimum cx (keeping cy unchanged)
        min_cx = _find_min_cx(text, font_pt, cy, max_cx)
        new_cx = min_cx

        # Step 2: center horizontally
        new_x = (SLIDE_W - new_cx) // 2
        new_cy = cy  # keep height unless text still doesn't fit

        if required_height_emu(text, font_pt, new_cx) > cy:
            # Even at max_cx text doesn't fit vertically — extend height
            new_cy = required_height_emu(text, font_pt, new_cx)
            fixes.append(
                f'RESIZE {name}: x {x}→{new_x}, cx {cx}→{new_cx}, cy {cy}→{new_cy} '
                f'(left={new_x/914400:.3f}" right={(SLIDE_W-new_x-new_cx)/914400:.3f}")'
            )
        else:
            fixes.append(
                f'WIDEN {name}: x {x}→{new_x}, cx {cx}→{new_cx} '
                f'(left={new_x/914400:.3f}" right={(SLIDE_W-new_x-new_cx)/914400:.3f}")'
            )

        _set_xfrm(sp, new_x, y, new_cx, new_cy)
        already_fixed.add(name)

        # Shift linked subtitle(s)
        _shift_linked(sp_map, name, new_x, y, new_cx, new_cy, fixes, already_fixed, margin_emu)

    return ET.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True), fixes


def _shift_linked(sp_map, title_name: str, tx, ty, tcx, tcy, fixes: list,
                  already_fixed: set, margin_emu: int):
    """
    Shift subtitle box down to avoid overlap with resized title.
    Applies same x/cx alignment as title for visual consistency.
    Also fixes subtitle's own overflow with the new cx.
    """
    title_bottom = ty + tcy
    gap = 91_440   # 0.1"
    max_cx = SLIDE_W - 2 * margin_emu

    for sub_name, sub_sp in sp_map.items():
        if sub_name == title_name or sub_name in already_fixed:
            continue
        _, sx, sy, scx, scy = _sp_info(sub_sp)
        if scx is None:
            continue
        stext, sfont = _sp_text_and_font(sub_sp)
        if not stext:
            continue
        # Subtitle heuristic: smaller font, positioned just below or overlapping title
        if not (sy >= ty and sy < title_bottom + gap * 5 and sfont < 40):
            continue

        new_sy = title_bottom + gap
        new_sx = tx       # align with title left
        new_scx = tcx     # same width as title

        # Check subtitle's own height with new cx
        new_scy = scy
        sub_req_h = required_height_emu(stext, sfont, new_scx)
        if sub_req_h > scy:
            new_scy = sub_req_h

        fixes.append(
            f'  ALIGN-SUBTITLE {sub_name}: x {sx}→{new_sx}, cx {scx}→{new_scx}, '
            f'y {sy}→{new_sy}, cy {scy}→{new_scy}'
        )
        _set_xfrm(sub_sp, new_sx, new_sy, new_scx, new_scy)
        already_fixed.add(sub_name)


# ── Main ─────────────────────────────────────────────────────────────────────

def run(path: str, fix: bool, slide_filter: int | None):
    pptx_path = Path(path)
    if not pptx_path.exists():
        print(f'ERROR: {path} not found')
        sys.exit(1)

    all_issues: list[dict] = []
    patch_map: dict[str, bytes] = {}

    with zipfile.ZipFile(pptx_path) as z:
        slide_names = sorted(
            n for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')
        )
        for sname in slide_names:
            idx = int(sname.replace('ppt/slides/slide', '').replace('.xml', ''))
            if slide_filter is not None and idx != slide_filter:
                continue
            raw = z.read(sname)
            issues = check_slide(raw, sname)
            for iss in issues:
                iss['slide_idx'] = idx
                iss['slide_path'] = sname
            all_issues.extend(issues)

    if not all_issues:
        print('✅ No textbox overflow detected.')
        return

    print(f'\n⚠️  Overflow detected in {len(all_issues)} shape(s):')
    for iss in all_issues:
        print(f"  Slide {iss['slide_idx']} / {iss['name']}: "
              f"{iss['n_lines']} lines, req_h={iss['req_height']} EMU > cy={iss['cy']} EMU "
              f"(font={iss['font_pt']}pt, text='{iss['text'][:40]}...')")

    if not fix:
        print('\nRun with --fix to auto-correct.')
        sys.exit(1)

    # Apply fixes
    affected_slides = set(iss['slide_path'] for iss in all_issues)
    with zipfile.ZipFile(pptx_path) as z:
        all_files = {n: z.read(n) for n in z.namelist()}

    for sname in affected_slides:
        raw = all_files[sname]
        patched, fix_msgs = fix_overflow(raw)
        all_files[sname] = patched
        for msg in fix_msgs:
            print(f'  FIX [{sname}]: {msg}')

    # Rewrite zip
    tmp_path = pptx_path.with_suffix('.overflow_fix.pptx')
    with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name, data in all_files.items():
            zout.writestr(name, data)
    tmp_path.replace(pptx_path)
    print(f'\n✅ Fixed and saved: {pptx_path}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('pptx')
    ap.add_argument('--fix', action='store_true')
    ap.add_argument('--slide', type=int, default=None)
    args = ap.parse_args()
    run(args.pptx, args.fix, args.slide)
