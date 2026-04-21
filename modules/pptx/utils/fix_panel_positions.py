"""
fix_panel_positions.py — roundRect 패널 내 TextBox 위치를 비율 기반으로 자동 수정.

사용법:
  python fix_panel_positions.py <file.pptx> [--slide N]

roundRect 패널이 감지된 슬라이드에서 내부 TextBox x/y/cx를 실측 비율로 자동 조정.
비율값: x=7.64%, title_y=11.77%, content_y=22.14% (2026-04-21 실측)

Option 1/2/3 파이프라인 4단계 필수 검증:
  1. pptx_integrity_check.py --fix
  2. verify_margins.py
  3. check_textbox_overflow.py --fix
  4. fix_panel_positions.py          ← 이 스크립트
"""

import argparse, sys, zipfile
import lxml.etree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pptx_safe_edit import check_text_corner_overlap, fix_text_corner_overlap


def run(pptx_path: str, slide_filter: int | None = None):
    path = Path(pptx_path)
    if not path.exists():
        print(f'ERROR: {pptx_path} not found')
        sys.exit(1)

    with zipfile.ZipFile(path) as z:
        all_files = {n: z.read(n) for n in z.namelist()}

    slide_names = sorted(
        n for n in all_files if n.startswith('ppt/slides/slide') and n.endswith('.xml')
    )

    total_fixes = []
    changed = False

    for sname in slide_names:
        idx = int(sname.replace('ppt/slides/slide', '').replace('.xml', ''))
        if slide_filter is not None and idx != slide_filter:
            continue

        root = ET.fromstring(all_files[sname])
        issues = check_text_corner_overlap(root, slide_idx=idx)
        if not issues:
            continue

        patched, fixes = fix_text_corner_overlap(root, slide_idx=idx)
        if fixes:
            all_files[sname] = patched
            changed = True
            for f in fixes:
                print(f'  [slide{idx}] {f}')
            total_fixes.extend(fixes)

    if not total_fixes:
        print('✅ No panel position adjustments needed.')
        return

    if changed:
        tmp = path.with_suffix('.tmp.pptx')
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
            for name, data in all_files.items():
                zout.writestr(name, data)
        tmp.replace(path)
        print(f'\n✅ Fixed {len(total_fixes)} TextBox(es) and saved: {path}')
    sys.exit(0)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('pptx')
    ap.add_argument('--slide', type=int, default=None)
    args = ap.parse_args()
    run(args.pptx, args.slide)
