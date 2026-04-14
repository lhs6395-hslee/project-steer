#!/usr/bin/env python3
"""
Reviewer verification script for slides idx 8 and idx 9.
Checks anchor values, fill types, and PNG icon presence.
"""

import json
import sys
import zipfile
from xml.etree import ElementTree as ET

PPTX_PATH = "/Users/toule/Documents/kiro/project-steer/results/pptx/AWS_MSK_Expert_Intro.pptx"

EMU_PER_INCH = 914400

# Namespace map (Clark notation helpers)
pNS = 'http://schemas.openxmlformats.org/presentationml/2006/main'
aNS = 'http://schemas.openxmlformats.org/drawingml/2006/main'
picNS = 'http://schemas.openxmlformats.org/drawingml/2006/picture'
rNS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

def p(tag): return f'{{{pNS}}}{tag}'
def a(tag): return f'{{{aNS}}}{tag}'
def pic(tag): return f'{{{picNS}}}{tag}'


def emu_to_inch(emu):
    return round(int(emu) / EMU_PER_INCH, 3)


def get_slide_xml(z, slide_index):
    """Get parsed XML for slide by 0-based index."""
    slide_name = f"ppt/slides/slide{slide_index + 1}.xml"
    with z.open(slide_name) as f:
        return ET.parse(f).getroot()


def get_all_shapes(root):
    """Return dict of {shape_name: {'element': el, 'type': 'sp'|'pic'}} from spTree."""
    shapes = {}

    # Find spTree
    spTree = root.find(f'.//{p("spTree")}')
    if spTree is None:
        print("  WARNING: spTree not found!")
        return shapes

    # sp elements (text boxes, auto shapes)
    for sp in spTree.findall(p('sp')):
        nvSpPr = sp.find(p('nvSpPr'))
        if nvSpPr is not None:
            cNvPr = nvSpPr.find(p('cNvPr'))
            if cNvPr is not None:
                name = cNvPr.get('name', '')
                shapes[name] = {'element': sp, 'type': 'sp'}

    # pic elements (images) — in presentationml namespace, not picture namespace
    for pi in spTree.findall(p('pic')):
        nvPicPr = pi.find(p('nvPicPr'))
        if nvPicPr is not None:
            cNvPr = nvPicPr.find(p('cNvPr'))
            if cNvPr is not None:
                name = cNvPr.get('name', '')
                shapes[name] = {'element': pi, 'type': 'pic'}

    return shapes


def get_anchor(sp_element):
    """Extract anchor (vert) from bodyPr in txBody."""
    txBody = sp_element.find(p('txBody'))
    if txBody is None:
        return None
    bodyPr = txBody.find(a('bodyPr'))
    if bodyPr is None:
        return None
    # Default anchor is 't' if attribute not set
    val = bodyPr.get('anchor', 't')
    return val


def get_fill_info(element, elem_type='sp'):
    """Extract fill info from spPr."""
    # Both sp and pic use pNS for spPr in OOXML presentations
    spPr = element.find(p('spPr'))
    if spPr is None:
        return {'type': 'no_spPr', 'color': None}

    # noFill
    noFill = spPr.find(a('noFill'))
    if noFill is not None:
        return {'type': 'noFill', 'color': None}

    # solidFill
    solidFill = spPr.find(a('solidFill'))
    if solidFill is not None:
        srgbClr = solidFill.find(a('srgbClr'))
        if srgbClr is not None:
            return {'type': 'solidFill', 'color': srgbClr.get('val', '').upper()}
        schemeClr = solidFill.find(a('schemeClr'))
        if schemeClr is not None:
            return {'type': 'solidFill', 'color': f'scheme:{schemeClr.get("val", "")}'}
        return {'type': 'solidFill', 'color': 'unknown'}

    gradFill = spPr.find(a('gradFill'))
    if gradFill is not None:
        return {'type': 'gradFill', 'color': None}

    pattFill = spPr.find(a('pattFill'))
    if pattFill is not None:
        return {'type': 'pattFill', 'color': None}

    # No explicit fill element = inherits from style/theme
    return {'type': 'inherited', 'color': None}


def get_position(element, elem_type='sp'):
    """Get position and size in inches from spPr/xfrm."""
    # Both sp and pic use pNS for spPr in OOXML presentations
    spPr = element.find(p('spPr'))

    if spPr is None:
        return None

    xfrm = spPr.find(a('xfrm'))
    if xfrm is None:
        return None

    off = xfrm.find(a('off'))
    ext = xfrm.find(a('ext'))
    if off is None or ext is None:
        return None

    return {
        'x': emu_to_inch(off.get('x', 0)),
        'y': emu_to_inch(off.get('y', 0)),
        'cx': emu_to_inch(ext.get('cx', 0)),
        'cy': emu_to_inch(ext.get('cy', 0))
    }


def find_shape(shapes, target_name):
    """Find shape by exact name, normalized match, or partial match."""
    # Exact match first
    if target_name in shapes:
        return shapes[target_name]
    # Normalize: remove spaces and lowercase for comparison
    target_norm = target_name.replace(' ', '').lower()
    for sname, sinfo in shapes.items():
        sname_norm = sname.replace(' ', '').lower()
        if target_norm == sname_norm:
            return sinfo
    # Partial match (target_name is substring of shape name)
    for sname, sinfo in shapes.items():
        if target_name in sname:
            return sinfo
    # Partial match (shape name is substring of target)
    for sname, sinfo in shapes.items():
        if sname in target_name:
            return sinfo
    return None


def check_icon(shapes):
    """Check for PNG icon at ~(10.5", 6.2"), ~0.6"x0.6"."""
    icon_found = False
    icon_details = []

    for name, info in shapes.items():
        if info['type'] == 'pic':
            pos = get_position(info['element'], 'pic')
            if pos:
                x_ok = abs(pos['x'] - 10.5) < 0.5
                y_ok = abs(pos['y'] - 6.2) < 0.5
                cx_ok = abs(pos['cx'] - 0.6) < 0.35
                cy_ok = abs(pos['cy'] - 0.6) < 0.35
                match = x_ok and y_ok and cx_ok and cy_ok
                icon_details.append({
                    'name': name,
                    'position': pos,
                    'matches_target': match
                })
                if match:
                    icon_found = True
            else:
                icon_details.append({'name': name, 'position': None, 'matches_target': False})

    return icon_found, icon_details


def verify_slide(z, slide_idx, contract):
    """Verify a slide against contract spec."""
    root = get_slide_xml(z, slide_idx)
    shapes = get_all_shapes(root)

    print(f"\n  Slide idx {slide_idx} shapes ({len(shapes)}): {sorted(shapes.keys())}")

    results = {
        'anchor_checks': {},
        'fill_checks': {},
        'icon': 'UNKNOWN',
        'icon_details': [],
        'shapes_found': sorted(shapes.keys())
    }
    issues = []

    # Anchor checks
    for tb_name, expected_anchor in contract['anchors'].items():
        found = find_shape(shapes, tb_name)

        if found is None:
            results['anchor_checks'][tb_name] = {
                'status': 'MISSING',
                'expected': expected_anchor,
                'actual': None
            }
            issues.append(f"[idx{slide_idx}] Shape '{tb_name}' not found")
            continue

        actual_anchor = get_anchor(found['element'])
        ok = (actual_anchor == expected_anchor)
        results['anchor_checks'][tb_name] = {
            'status': 'PASS' if ok else 'FAIL',
            'expected': expected_anchor,
            'actual': actual_anchor
        }
        if not ok:
            issues.append(f"[idx{slide_idx}] {tb_name}: anchor expected='{expected_anchor}', actual='{actual_anchor}'")

    # Fill checks
    for shape_name, expected_fill in contract['fills'].items():
        found = find_shape(shapes, shape_name)

        if found is None:
            results['fill_checks'][shape_name] = {
                'status': 'MISSING',
                'expected': expected_fill,
                'actual': None
            }
            issues.append(f"[idx{slide_idx}] Shape '{shape_name}' not found")
            continue

        fill_info = get_fill_info(found['element'], found['type'])

        if expected_fill == 'noFill':
            ok = (fill_info['type'] == 'noFill')
        elif expected_fill.startswith('#'):
            expected_hex = expected_fill.lstrip('#').upper()
            ok = (fill_info['type'] == 'solidFill' and fill_info['color'] == expected_hex)
        else:
            ok = False

        results['fill_checks'][shape_name] = {
            'status': 'PASS' if ok else 'FAIL',
            'expected': expected_fill,
            'actual': fill_info
        }
        if not ok:
            issues.append(f"[idx{slide_idx}] {shape_name}: fill expected='{expected_fill}', actual={fill_info}")

    # Icon check
    icon_found, icon_details = check_icon(shapes)
    results['icon'] = 'PASS' if icon_found else 'FAIL'
    results['icon_details'] = icon_details

    if not icon_found:
        pic_shapes = {k: v for k, v in shapes.items() if v['type'] == 'pic'}
        if pic_shapes:
            issues.append(f"[idx{slide_idx}] PNG icon not found at ~(10.5\", 6.2\"). Found pictures: {list(pic_shapes.keys())}, details: {icon_details}")
        else:
            issues.append(f"[idx{slide_idx}] No PICTURE shapes found on slide")

    return results, issues


def main():
    # Sprint_Contract for slide idx 8 (L04 Process Arrow)
    slide8_contract = {
        'anchors': {
            'TextBox 7': 't',
            'TextBox 11': 't',
            'TextBox 15': 't',
            'TextBox 19': 't',
            'TextBox 5': 'ctr',
            'TextBox 9': 'ctr',
            'TextBox 13': 'ctr',
            'TextBox 17': 'ctr',
        },
        'fills': {
            'TextBox 7': 'noFill',
            'TextBox 11': 'noFill',
            'TextBox 15': 'noFill',
            'TextBox 19': 'noFill',
            'TextBox 20': 'noFill',
            'TextBox 21': 'noFill',
        }
    }

    # Sprint_Contract for slide idx 9 (L05 Phased Columns)
    slide9_contract = {
        'anchors': {
            'TextBox 7': 't',
            'TextBox 11': 't',
            'TextBox 15': 't',
            'TextBox 19': 't',
            'TextBox 5': 'ctr',
            'TextBox 9': 'ctr',
            'TextBox 13': 'ctr',
            'TextBox 17': 'ctr',
        },
        'fills': {
            'TextBox 7': 'noFill',
            'TextBox 11': 'noFill',
            'TextBox 15': 'noFill',
            'TextBox 19': 'noFill',
            'TextBox 21': 'noFill',
            # Phase header Rounded Rectangles (actual names have space)
            'Rounded Rectangle 4': '#001B5E',
            'Rounded Rectangle 8': '#0043DA',
            'Rounded Rectangle 12': '#EE8150',
            'Rounded Rectangle 16': '#4CB88F',
            # Phase header TextBoxes - solid fills
            'TextBox 5': '#001B5E',
            'TextBox 9': '#0043DA',
            'TextBox 13': '#EE8150',
            'TextBox 17': '#4CB88F',
            # Content card Rounded Rectangles
            'Rounded Rectangle 6': '#F8F9FA',
            'Rounded Rectangle 10': '#F8F9FA',
            'Rounded Rectangle 14': '#F8F9FA',
            'Rounded Rectangle 18': '#F8F9FA',
        }
    }

    try:
        with zipfile.ZipFile(PPTX_PATH, 'r') as z:
            slide_files = sorted([n for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')])
            print(f"Total slides found: {len(slide_files)}")

            slide8_results, slide8_issues = verify_slide(z, 8, slide8_contract)
            slide9_results, slide9_issues = verify_slide(z, 9, slide9_contract)

    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)

    all_issues = slide8_issues + slide9_issues

    # Count pass/fail
    def count_checks(results):
        total = 0
        passed = 0
        for d in [results['anchor_checks'], results['fill_checks']]:
            for v in d.values():
                total += 1
                if v['status'] == 'PASS':
                    passed += 1
        total += 1  # icon
        if results['icon'] == 'PASS':
            passed += 1
        return total, passed

    t8, p8 = count_checks(slide8_results)
    t9, p9 = count_checks(slide9_results)
    total = t8 + t9
    passed = p8 + p9
    confidence = round(passed / total, 3) if total > 0 else 0.0

    slide8_ok = (p8 == t8)
    slide9_ok = (p9 == t9)
    overall_verdict = "PASS" if (slide8_ok and slide9_ok) else "FAIL"

    # Build slide-level summaries
    def slide_summary(res, total, passed):
        anchor_pass = all(v['status'] == 'PASS' for v in res['anchor_checks'].values())
        fill_pass = all(v['status'] == 'PASS' for v in res['fill_checks'].values())
        return {
            "overall": "PASS" if (anchor_pass and fill_pass and res['icon'] == 'PASS') else "FAIL",
            "anchor_checks": res['anchor_checks'],
            "fill_checks": res['fill_checks'],
            "icon": res['icon'],
            "icon_details": res['icon_details'],
            "shapes_found": res['shapes_found'],
            f"checks_{passed}/{total}": f"{passed}/{total}"
        }

    verdict = {
        "verdict": overall_verdict,
        "confidence": confidence,
        "slide_idx8": slide_summary(slide8_results, t8, p8),
        "slide_idx9": slide_summary(slide9_results, t9, p9),
        "issues": all_issues,
        "fix_required": all_issues  # same list, executor uses this
    }

    print("\n" + "=" * 60)
    print("VERDICT JSON:")
    print("=" * 60)
    print(json.dumps(verdict, indent=2, ensure_ascii=False))

    return 0 if overall_verdict == "PASS" else 1


if __name__ == '__main__':
    sys.exit(main())
