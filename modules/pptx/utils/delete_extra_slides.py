"""
delete_extra_slides.py
──────────────────────
Removes all slides from a PPTX except the one at keep_index (default=0).
Uses direct XML manipulation via lxml to remove slide references from
the presentation relationship and sldIdLst elements.

Usage:
    python modules/pptx/utils/delete_extra_slides.py <pptx_path> [keep_index]

Example:
    python modules/pptx/utils/delete_extra_slides.py output/pipeline_test.pptx 0
"""

import sys
import zipfile
import shutil
import os
import re
from lxml import etree


NSMAP = {
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
}
RELS_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'


def delete_extra_slides(pptx_path: str, keep_index: int = 0, output_path: str | None = None):
    """
    Keep only the slide at keep_index; remove all others by:
    1. Parsing ppt/presentation.xml → sldIdLst to find slide rIds
    2. Parsing ppt/_rels/presentation.xml.rels to map rId → slide file
    3. Rebuilding the zip without removed slide parts and their rels
    4. Updating presentation.xml and presentation.xml.rels accordingly
    """
    if output_path is None:
        output_path = pptx_path

    # Work on a temporary copy if in-place
    tmp_path = pptx_path + ".tmp_deledit"
    shutil.copy2(pptx_path, tmp_path)

    try:
        with zipfile.ZipFile(tmp_path, 'r') as zin:
            namelist = zin.namelist()

            # ── Parse presentation.xml ──────────────────────────────────────
            prs_xml = zin.read('ppt/presentation.xml')
            prs_tree = etree.fromstring(prs_xml)

            sldIdLst = prs_tree.find(
                './/p:sldIdLst',
                namespaces={'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}
            )
            R_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
            sldId_elems = list(sldIdLst)
            total_before = len(sldId_elems)
            print(f"[INFO] Total slides before: {total_before}")

            # ── Parse presentation.xml.rels ─────────────────────────────────
            prs_rels_xml = zin.read('ppt/_rels/presentation.xml.rels')
            prs_rels_tree = etree.fromstring(prs_rels_xml)
            # Map rId → target (e.g. 'slides/slide1.xml')
            rid_to_target = {}
            for rel in prs_rels_tree:
                rid = rel.get('Id')
                target = rel.get('Target')
                if target and target.startswith('slides/'):
                    rid_to_target[rid] = target

            # ── Determine which slides to keep / remove ─────────────────────
            keep_elem = sldId_elems[keep_index]
            keep_rId = keep_elem.get(f'{{{R_NS}}}id')
            keep_target = rid_to_target.get(keep_rId)
            print(f"[KEEP] Slide {keep_index}: rId={keep_rId}, target={keep_target}")

            remove_rIds = set()
            remove_targets = set()
            for i, elem in enumerate(sldId_elems):
                if i == keep_index:
                    continue
                rId = elem.get(f'{{{R_NS}}}id')
                target = rid_to_target.get(rId, '')
                remove_rIds.add(rId)
                if target:
                    remove_targets.add('ppt/' + target)
                    # Also remove that slide's own .rels file
                    slide_name = os.path.basename(target)
                    remove_targets.add(f'ppt/slides/_rels/{slide_name}.rels')
                sldIdLst.remove(elem)
                print(f"[REMOVED] Slide {i}: rId={rId}, target={target}")

            # ── Update presentation.xml.rels (remove rel entries) ───────────
            for rel in list(prs_rels_tree):
                if rel.get('Id') in remove_rIds:
                    prs_rels_tree.remove(rel)

            updated_prs_xml = etree.tostring(prs_tree, xml_declaration=True,
                                              encoding='UTF-8', standalone=True)
            updated_prs_rels_xml = etree.tostring(prs_rels_tree, xml_declaration=True,
                                                   encoding='UTF-8', standalone=True)

            # ── Write new zip ───────────────────────────────────────────────
            out_tmp = output_path + ".out_tmp"
            with zipfile.ZipFile(tmp_path, 'r') as zin2, \
                 zipfile.ZipFile(out_tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
                for item in zin2.infolist():
                    name = item.filename
                    if name in remove_targets:
                        print(f"[ZIP-SKIP] {name}")
                        continue
                    if name == 'ppt/presentation.xml':
                        zout.writestr(item, updated_prs_xml)
                    elif name == 'ppt/_rels/presentation.xml.rels':
                        zout.writestr(item, updated_prs_rels_xml)
                    else:
                        zout.writestr(item, zin2.read(name))

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # Replace original with output
    shutil.move(out_tmp, output_path)

    # ── Verify ──────────────────────────────────────────────────────────────
    from pptx import Presentation as PRS
    prs2 = PRS(output_path)
    total_after = len(prs2.slides)
    print(f"\n[RESULT] Slides after save: {total_after}")
    for i, slide in enumerate(prs2.slides):
        print(f"  Slide {i}: layout={slide.slide_layout.name}")

    if total_after == 1:
        print("[SUCCESS] Exactly 1 slide remains.")
    else:
        print(f"[FAIL] Expected 1 slide but got {total_after}.")
        sys.exit(1)


if __name__ == "__main__":
    pptx_path = sys.argv[1] if len(sys.argv) > 1 else "output/pipeline_test.pptx"
    keep_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    delete_extra_slides(pptx_path, keep_index=keep_idx)
