#!/usr/bin/env python3
"""
Slide reorder utility: move ending slide to last position.
Usage: python reorder_slides.py <pptx_path>

After MCP adds a new body slide (goes to end = index 3),
the ending slide (currently at index 2) must be moved to last.

Before: [Cover(0), TOC(1), Ending(2), L03(3)]
After:  [Cover(0), TOC(1), L03(2), Ending(3)]
"""

import sys
import os
import copy
from lxml import etree

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pptx import Presentation
from pptx.util import Inches, Pt, Emu


def move_slide(prs, from_idx: int, to_idx: int):
    """Move slide from_idx to to_idx position."""
    xml_slides = prs.slides._sldIdLst
    slides = list(xml_slides)
    slide = slides[from_idx]
    xml_slides.remove(slide)
    xml_slides.insert(to_idx, slide)


def reorder_for_ending_last(pptx_path: str):
    """Move ending slide from index 2 to last position."""
    prs = Presentation(pptx_path)
    n = len(prs.slides)
    print(f"Slides before reorder: {n}")
    for i, slide in enumerate(prs.slides):
        layout = slide.slide_layout.name if slide.slide_layout else "unknown"
        print(f"  [{i}] layout={layout}")

    # Find ending slide (layout='끝맺음')
    ending_idx = None
    for i, slide in enumerate(prs.slides):
        layout = slide.slide_layout.name if slide.slide_layout else ""
        if layout == "끝맺음":
            ending_idx = i
            break

    if ending_idx is None:
        print("ERROR: 끝맺음 slide not found!")
        return False

    if ending_idx == n - 1:
        print(f"Ending slide already at last position ({ending_idx}). No reorder needed.")
        return True

    print(f"\nMoving ending slide from index {ending_idx} to last (index {n-1})")
    move_slide(prs, ending_idx, n - 1)

    print(f"\nSlides after reorder: {len(prs.slides)}")
    for i, slide in enumerate(prs.slides):
        layout = slide.slide_layout.name if slide.slide_layout else "unknown"
        print(f"  [{i}] layout={layout}")

    prs.save(pptx_path)
    print(f"\nSaved: {pptx_path}")
    return True


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/Users/toule/Documents/gsneotek/kiro/project-steer/results/pptx/AWS_MSK_Expert_Intro.pptx"
    reorder_for_ending_last(path)
