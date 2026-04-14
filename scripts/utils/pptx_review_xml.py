#!/usr/bin/env python3
"""
PPTX Review with XML-based Theme Color Resolution
Uses zipfile to extract and parse theme1.xml directly
"""

import sys
import zipfile
import xml.etree.ElementTree as ET
import json
from pathlib import Path
from typing import Dict, Tuple, Optional

def parse_theme_colors_from_zip(pptx_path: str) -> Dict[str, Tuple[int, int, int]]:
    """
    Extract theme colors by reading theme1.xml from PPTX zip
    """
    theme_colors = {}
    
    try:
        with zipfile.ZipFile(pptx_path, 'r') as zf:
            # Read theme XML
            theme_xml = zf.read('ppt/theme/theme1.xml')
            root = ET.fromstring(theme_xml)
            
            # Namespace
            ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
            
            # Find color scheme
            clr_scheme = root.find('.//a:clrScheme', ns)
            
            if clr_scheme is not None:
                for elem in clr_scheme:
                    tag = elem.tag.split('}')[-1]
                    
                    # Try srgbClr
                    srgb = elem.find('a:srgbClr', ns)
                    if srgb is not None and 'val' in srgb.attrib:
                        hex_val = srgb.attrib['val']
                        rgb = tuple(int(hex_val[i:i+2], 16) for i in (0, 2, 4))
                        theme_colors[tag] = rgb
                        continue
                    
                    # Try sysClr
                    sys_clr = elem.find('a:sysClr', ns)
                    if sys_clr is not None and 'lastClr' in sys_clr.attrib:
                        hex_val = sys_clr.attrib['lastClr']
                        rgb = tuple(int(hex_val[i:i+2], 16) for i in (0, 2, 4))
                        theme_colors[tag] = rgb
        
        print(f"[INFO] Extracted {len(theme_colors)} theme colors")
        for name, rgb in theme_colors.items():
            print(f"  {name}: RGB{rgb}")
        
    except Exception as e:
        print(f"[ERROR] Failed to parse theme colors: {e}")
        # Fallback defaults
        theme_colors = {
            'dk1': (0, 0, 0),
            'lt1': (255, 255, 255),
            'dk2': (68, 114, 196),
            'lt2': (237, 125, 49),
            'accent1': (68, 114, 196),
            'accent2': (237, 125, 49)
        }
    
    return theme_colors

def find_template_files(search_paths):
    """Search for template PPTX in standard locations"""
    found = []
    
    for path in search_paths:
        p = Path(path)
        if p.exists():
            if p.is_file():
                found.append(str(p))
            elif p.is_dir():
                # Search for pptx files
                for pptx_file in p.glob('*.pptx'):
                    if 'template' in pptx_file.name.lower():
                        found.append(str(pptx_file))
    
    return found

if __name__ == '__main__':
    target_path = 'results/pptx/AWS_MSK_Expert_Intro.pptx'
    
    print("=" * 80)
    print("PPTX REVIEW - THEME COLOR EXTRACTION")
    print("=" * 80)
    
    # Extract theme colors
    print(f"\n[STEP 1] Extracting theme colors from: {target_path}")
    theme_colors = parse_theme_colors_from_zip(target_path)
    
    # Search for template
    print(f"\n[STEP 2] Searching for template baseline...")
    search_paths = [
        'templates/pptx_template.pptx',
        'templates/',
        'results/pptx/templates/',
        './pptx_template.pptx'
    ]
    
    found_templates = find_template_files(search_paths)
    print(f"[INFO] Found {len(found_templates)} template files:")
    for tmpl in found_templates:
        print(f"  - {tmpl}")
    
    # Generate report
    report = {
        'target_file': target_path,
        'theme_colors_extracted': theme_colors,
        'template_search_paths': search_paths,
        'templates_found': found_templates,
        'status': 'success' if theme_colors else 'failed'
    }
    
    output_path = 'results/theme_color_extraction.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n[COMPLETE] Report saved to: {output_path}")

