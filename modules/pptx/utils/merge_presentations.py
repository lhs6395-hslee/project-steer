#!/usr/bin/env python3
"""
merge_presentations.py — L01~L05 work.pptx의 슬라이드 41(index)을 추출하여
results/pptx/AWS_MSK_Expert_Intro.pptx에 삽입.

zipfile 기반으로 python-pptx 내부 구조를 직접 조작하여 안정적으로 병합.
"""

import zipfile
import shutil
import re
import os
import copy
from pathlib import Path
from lxml import etree as ET

BASE_DIR = Path(__file__).parent.parent.parent
PIPELINE_DIR = BASE_DIR / ".pipeline" / "pptx"
RESULTS_DIR = BASE_DIR / "results" / "pptx"
SOURCE_PPTX = RESULTS_DIR / "AWS_MSK_Expert_Intro.pptx"

LAYOUT_FILES = [
    PIPELINE_DIR / "L01_work.pptx",
    PIPELINE_DIR / "L02_work.pptx",
    PIPELINE_DIR / "L03_work.pptx",
    PIPELINE_DIR / "L04_work.pptx",
    PIPELINE_DIR / "L05_work.pptx",
]

WORK_SLIDE_INDEX = 41  # 0-based

NS = {
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
}

PRS_NS = 'http://schemas.openxmlformats.org/presentationml/2006/main'
REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
SLIDE_REL_TYPE = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide'


def get_slide_filename(pptx_path: Path, slide_idx: int) -> str:
    """Get the actual slide XML filename for a given 0-based slide index."""
    with zipfile.ZipFile(pptx_path) as z:
        prs_xml = ET.fromstring(z.read('ppt/presentation.xml'))
        rels_xml = ET.fromstring(z.read('ppt/_rels/presentation.xml.rels'))

        # Get all slide IDs in order
        sldIdLst = prs_xml.find(f'{{{PRS_NS}}}sldIdLst')
        slide_ids = sldIdLst.findall(f'{{{PRS_NS}}}sldId')

        if slide_idx >= len(slide_ids):
            raise IndexError(f"slide_idx={slide_idx} >= slide count={len(slide_ids)}")

        target_id = slide_ids[slide_idx]
        r_id = target_id.get(f'{{{REL_NS}}}id')

        # Find the relationship target
        for rel in rels_xml:
            if rel.get('Id') == r_id and rel.get('Type') == SLIDE_REL_TYPE:
                target = rel.get('Target')  # e.g. "slides/slide42.xml"
                return target

    raise ValueError(f"Could not find slide {slide_idx} in {pptx_path}")


def get_slide_rels_filename(slide_filename: str) -> str:
    """Get _rels path from slide path. e.g. slides/slide42.xml -> slides/_rels/slide42.xml.rels"""
    parts = slide_filename.rsplit('/', 1)
    if len(parts) == 2:
        return f"{parts[0]}/_rels/{parts[1]}.rels"
    return f"_rels/{slide_filename}.rels"


def get_next_slide_num(existing_names: list) -> int:
    """Find the next available slide number from existing slide file names."""
    nums = []
    for name in existing_names:
        m = re.search(r'slide(\d+)\.xml$', name)
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1 if nums else 1


def merge():
    print("=== Merge L01~L05 into AWS_MSK_Expert_Intro.pptx (zipfile method) ===")

    # Backup source
    backup = SOURCE_PPTX.with_suffix('.pptx.bak')
    shutil.copy2(str(SOURCE_PPTX), str(backup))
    print(f"Backup: {backup}")

    tmp_out = SOURCE_PPTX.with_suffix('.pptx.tmp')

    # Get info from source
    with zipfile.ZipFile(str(SOURCE_PPTX)) as src_z:
        src_names = src_z.namelist()
        src_prs_xml = ET.fromstring(src_z.read('ppt/presentation.xml'))
        src_prs_rels = ET.fromstring(src_z.read('ppt/_rels/presentation.xml.rels'))

        # Find existing slide count
        src_sldIdLst = src_prs_xml.find(f'{{{PRS_NS}}}sldIdLst')
        src_slide_ids = src_sldIdLst.findall(f'{{{PRS_NS}}}sldId')
        print(f"Source slides: {len(src_slide_ids)}")

        # Find max sldId value
        max_id = max(int(s.get('id')) for s in src_slide_ids)

        # Find existing relationship max ID
        max_r_num = 0
        for rel in src_prs_rels:
            m = re.match(r'rId(\d+)', rel.get('Id', ''))
            if m:
                max_r_num = max(max_r_num, int(m.group(1)))

        # Find next slide number
        existing_slide_names = [n for n in src_names if re.match(r'ppt/slides/slide\d+\.xml$', n)]
        next_slide_num = get_next_slide_num(existing_slide_names)

        # Prepare new slide data from work files
        new_slides = []
        for work_file in LAYOUT_FILES:
            slide_fname = get_slide_filename(work_file, WORK_SLIDE_INDEX)
            rels_fname = get_slide_rels_filename(slide_fname)
            full_slide = f"ppt/{slide_fname}"
            full_rels = f"ppt/{rels_fname}"

            with zipfile.ZipFile(str(work_file)) as wz:
                slide_xml = wz.read(full_slide)
                try:
                    rels_xml = wz.read(full_rels)
                except KeyError:
                    rels_xml = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'

                # Collect media files referenced in slide rels
                media_files = {}
                rels_tree = ET.fromstring(rels_xml)
                for rel in rels_tree:
                    target = rel.get('Target', '')
                    if target.startswith('../media/'):
                        media_name = target.replace('../media/', 'ppt/media/')
                        try:
                            media_data = wz.read(media_name)
                            media_files[media_name] = media_data
                        except KeyError:
                            pass

            new_slides.append({
                'name': work_file.stem,
                'slide_xml': slide_xml,
                'rels_xml': rels_xml,
                'media': media_files,
            })
            print(f"  Extracted: {work_file.stem} slide {WORK_SLIDE_INDEX} ({len(media_files)} media files)")

    # Build new zip
    with zipfile.ZipFile(str(SOURCE_PPTX)) as src_z, \
         zipfile.ZipFile(str(tmp_out), 'w', zipfile.ZIP_DEFLATED) as out_z:

        # Copy all existing files (except presentation.xml, its rels, and Content_Types - we'll update those)
        skip = {'ppt/presentation.xml', 'ppt/_rels/presentation.xml.rels', '[Content_Types].xml'}
        copied_media = set()

        seen_names = set()
        for name in src_z.namelist():
            if name not in skip and name not in seen_names:
                seen_names.add(name)
                out_z.writestr(name, src_z.read(name))

        # Load Content_Types for update
        SLIDE_CT = 'application/vnd.openxmlformats-officedocument.presentationml.slide+xml'
        ct_xml = ET.fromstring(src_z.read('[Content_Types].xml'))
        existing_ct_parts = {el.get('PartName', '') for el in ct_xml}

        # Add new slide files
        added_media = set()
        slide_additions = []  # (sld_id, r_id, slide_file_path)

        for i, slide_data in enumerate(new_slides):
            new_slide_num = next_slide_num + i
            new_slide_name = f"ppt/slides/slide{new_slide_num}.xml"
            new_rels_name = f"ppt/slides/_rels/slide{new_slide_num}.xml.rels"

            # Update rels to point to correct media paths (they stay the same ../media/)
            out_z.writestr(new_slide_name, slide_data['slide_xml'])
            out_z.writestr(new_rels_name, slide_data['rels_xml'])

            # Add media files if not already added
            for media_name, media_data in slide_data['media'].items():
                if media_name not in added_media:
                    # Check if already in source
                    if media_name not in src_z.namelist():
                        out_z.writestr(media_name, media_data)
                    added_media.add(media_name)

            # Track for presentation.xml update
            max_id += 1
            max_r_num += 1
            r_id = f"rId{max_r_num}"
            slide_additions.append({
                'sld_id': max_id,
                'r_id': r_id,
                'target': f"slides/slide{new_slide_num}.xml",
                'name': slide_data['name'],
            })
            print(f"  Written: slide{new_slide_num}.xml ({slide_data['name']})")

            # Register slide in Content_Types if missing
            ct_part = f'/ppt/slides/slide{new_slide_num}.xml'
            if ct_part not in existing_ct_parts:
                override = ET.SubElement(ct_xml, 'Override')
                override.set('PartName', ct_part)
                override.set('ContentType', SLIDE_CT)
                existing_ct_parts.add(ct_part)

        # Write updated Content_Types
        ct_bytes = ET.tostring(ct_xml, xml_declaration=True, encoding='UTF-8', standalone=True)
        out_z.writestr('[Content_Types].xml', ct_bytes)

        # Update presentation.xml — add new sldId entries before thank-you slide
        # Insert new slides after index 1 (toc), before last slide (thank-you)
        insert_pos = len(src_slide_ids) - 1  # before last slide
        if insert_pos < 2:
            insert_pos = len(src_slide_ids)  # append at end if too few slides

        for j, addition in enumerate(slide_additions):
            new_sld_id = ET.SubElement(src_sldIdLst, f'{{{PRS_NS}}}sldId')
            new_sld_id.set('id', str(addition['sld_id']))
            new_sld_id.set(f'{{{REL_NS}}}id', addition['r_id'])

            # Move the new element to insert_pos
            src_slide_ids_now = src_sldIdLst.findall(f'{{{PRS_NS}}}sldId')
            src_sldIdLst.remove(new_sld_id)
            src_sldIdLst.insert(insert_pos + j, new_sld_id)

        # Write updated presentation.xml
        prs_xml_bytes = ET.tostring(src_prs_xml, xml_declaration=True, encoding='UTF-8', standalone=True)
        out_z.writestr('ppt/presentation.xml', prs_xml_bytes)

        # Update _rels/presentation.xml.rels — add new slide relationships
        for addition in slide_additions:
            new_rel = ET.SubElement(src_prs_rels, 'Relationship')
            new_rel.set('Id', addition['r_id'])
            new_rel.set('Type', SLIDE_REL_TYPE)
            new_rel.set('Target', addition['target'])

        rels_xml_bytes = ET.tostring(src_prs_rels, xml_declaration=True, encoding='UTF-8', standalone=True)
        out_z.writestr('ppt/_rels/presentation.xml.rels', rels_xml_bytes)

    # Atomic replace
    os.replace(str(tmp_out), str(SOURCE_PPTX))
    print(f"\nSaved: {SOURCE_PPTX}")

    # Verify
    with zipfile.ZipFile(str(SOURCE_PPTX)) as z:
        prs = ET.fromstring(z.read('ppt/presentation.xml'))
        sld_ids = prs.find(f'{{{PRS_NS}}}sldIdLst').findall(f'{{{PRS_NS}}}sldId')
        print(f"Final slide count: {len(sld_ids)}")

    # Remove backup on success
    backup.unlink()
    print("Done.")
    return True


if __name__ == "__main__":
    success = merge()
    exit(0 if success else 1)
