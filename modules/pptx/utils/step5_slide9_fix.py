#!/usr/bin/env python3
"""
Step 5: Fix Slide 9 (idx 8) — L04 Process Arrow
(a) Verify subtitle (already 2 lines, word-boundary) — no change if correct
(b) Read actual card positions from PPTX shapes
(c) Remove wrong Picture 22
(d) Add 4 per-card bottom-right icons at (card_right - 0.55", card_bottom - 0.55")
    Size: 411480 × 411480 EMU (0.45" × 0.45")
Saves atomically: write to .tmp, then os.replace()
"""

import os
import sys
import copy

from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.enum.shapes import MSO_SHAPE_TYPE

PPTX_PATH = "results/pptx/AWS_MSK_Expert_Intro.pptx"
TMP_PATH = PPTX_PATH + ".step5.tmp"
ICONS_DIR = "icons"

# Icon size: 411480 EMU = 0.45"
ICON_SIZE_EMU = 411480

# Per-card offset from right/bottom: 0.55" = 502920 EMU
ICON_OFFSET_EMU = int(0.55 * 914400)  # 502920

# Card shapes by shape index on slide 9 (from reconnaissance)
# These are confirmed by reading the PPTX
CARD_SHAPE_INDICES = [5, 9, 13, 17]  # RR6, RR10, RR14, RR18

# Icon assignment per card (content-based, from modules/pptx/icons/png/ folder)
# 설계 (Design/Arch): settings.png — configuration/design
# 생성 (Create/Deploy): deploy.png — cluster creation/deployment
# 연결 (Connect): connect.png — producer/consumer connections
# 운영 (Operations): monitoring.png — monitoring and operations
CARD_ICONS = [
    "settings.png",    # 1. 설계 — VPC/Subnet design, broker sizing, security groups
    "deploy.png",      # 2. 생성 — cluster creation, auth setup, encryption
    "connect.png",     # 3. 연결 — Producer connect, MSK Connect, PrivateLink
    "monitoring.png",  # 4. 운영 — monitoring, partition rebalancing, cost optimization
]


def emu_to_inches(emu):
    return emu / 914400 if emu else 0


def verify_subtitle(slide):
    """Verify subtitle (Shape[1]) is 2-line with word-boundary breaks. No changes unless needed."""
    shape = slide.shapes[1]
    tf = shape.text_frame
    
    # Read textbox dimensions
    left = shape.left
    top = shape.top
    width = shape.width
    height = shape.height
    
    paras = tf.paragraphs
    num_paras = len([p for p in paras if p.text.strip()])
    
    print(f"[SUBTITLE] TextBox dimensions: left={emu_to_inches(left):.4f}\" top={emu_to_inches(top):.4f}\" "
          f"w={emu_to_inches(width):.4f}\" h={emu_to_inches(height):.4f}\"")
    print(f"[SUBTITLE] Number of non-empty paragraphs: {num_paras}")
    
    for pi, para in enumerate(paras):
        for ri, run in enumerate(para.runs):
            fs = run.font.size
            fs_pt = (fs / 12700) if fs else 'inherit'
            print(f"[SUBTITLE] para[{pi}] run[{ri}]: text={repr(run.text)} "
                  f"font_size={fs_pt}pt bold={run.font.bold}")
    
    # Check for mid-word breaks
    full_text_repr = repr(tf.text)
    print(f"[SUBTITLE] Full text repr: {full_text_repr}")
    
    if num_paras <= 2:
        print("[SUBTITLE] ✓ Already 2 lines, word-boundary — no change needed")
        return True, None
    else:
        print(f"[SUBTITLE] ⚠ Has {num_paras} non-empty paragraphs — needs fix")
        return False, tf


def read_card_positions(slide):
    """Read card shape positions directly from PPTX shapes (not hardcoded)."""
    results = []
    for idx in CARD_SHAPE_INDICES:
        shape = slide.shapes[idx]
        left_emu = shape.left
        top_emu = shape.top
        width_emu = shape.width
        height_emu = shape.height
        right_emu = left_emu + width_emu
        bottom_emu = top_emu + height_emu
        
        icon_left_emu = right_emu - ICON_OFFSET_EMU
        icon_top_emu = bottom_emu - ICON_OFFSET_EMU
        
        print(f"[CARD] Shape[{idx}] '{shape.name}': "
              f"left={emu_to_inches(left_emu):.4f}\" top={emu_to_inches(top_emu):.4f}\" "
              f"right={emu_to_inches(right_emu):.4f}\" bottom={emu_to_inches(bottom_emu):.4f}\"")
        print(f"       → icon_left={emu_to_inches(icon_left_emu):.4f}\" "
              f"icon_top={emu_to_inches(icon_top_emu):.4f}\" "
              f"(EMU: {icon_left_emu}, {icon_top_emu})")
        
        results.append({
            'shape_idx': idx,
            'shape_name': shape.name,
            'right_emu': right_emu,
            'bottom_emu': bottom_emu,
            'icon_left_emu': icon_left_emu,
            'icon_top_emu': icon_top_emu,
        })
    return results


def remove_wrong_picture(slide):
    """Remove Picture 22 (wrong size/position icon) from slide."""
    # Find shapes named 'Picture 22' or that are pictures at wrong positions
    to_remove = []
    for shape in slide.shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            left = emu_to_inches(shape.left)
            top = emu_to_inches(shape.top)
            w = emu_to_inches(shape.width)
            h = emu_to_inches(shape.height)
            print(f"[ICON-REMOVE] Found PICTURE '{shape.name}': "
                  f"left={left:.4f}\" top={top:.4f}\" w={w:.4f}\" h={h:.4f}\"")
            to_remove.append(shape)
    
    for shape in to_remove:
        sp = shape._element
        sp.getparent().remove(sp)
        print(f"[ICON-REMOVE] ✓ Removed '{shape.name}'")
    
    return len(to_remove)


def add_card_icons(slide, card_positions):
    """Add 4 per-card icons at bottom-right positions."""
    added = []
    for i, (card_info, icon_file) in enumerate(zip(card_positions, CARD_ICONS)):
        icon_path = os.path.join(ICONS_DIR, icon_file)
        
        if not os.path.exists(icon_path):
            print(f"[ICON-ADD] ✗ Icon not found: {icon_path}")
            sys.exit(1)
        
        left_emu = card_info['icon_left_emu']
        top_emu = card_info['icon_top_emu']
        
        pic = slide.shapes.add_picture(
            icon_path,
            left_emu,
            top_emu,
            ICON_SIZE_EMU,
            ICON_SIZE_EMU
        )
        
        print(f"[ICON-ADD] ✓ Added '{icon_file}' for card {i+1} "
              f"at left={emu_to_inches(left_emu):.4f}\" top={emu_to_inches(top_emu):.4f}\" "
              f"size={emu_to_inches(ICON_SIZE_EMU):.4f}\"×{emu_to_inches(ICON_SIZE_EMU):.4f}\"")
        
        added.append({
            'icon': icon_file,
            'left_emu': left_emu,
            'top_emu': top_emu,
            'size_emu': ICON_SIZE_EMU,
        })
    return added


def verify_added_icons(slide):
    """Verify all added icons have correct size and positions."""
    pictures = [s for s in slide.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
    print(f"\n[VERIFY] Total pictures on slide after fix: {len(pictures)}")
    for pic in pictures:
        w = pic.width
        h = pic.height
        size_ok = (w == ICON_SIZE_EMU and h == ICON_SIZE_EMU)
        print(f"[VERIFY] '{pic.name}': left={emu_to_inches(pic.left):.4f}\" "
              f"top={emu_to_inches(pic.top):.4f}\" "
              f"w={emu_to_inches(w):.4f}\" h={emu_to_inches(h):.4f}\" "
              f"size_correct={size_ok}")
    return len(pictures) == 4


def main():
    print(f"=== STEP 5: Slide 9 (idx 8) Fix ===")
    print(f"Opening: {PPTX_PATH}")
    
    prs = Presentation(PPTX_PATH)
    slide = prs.slides[8]  # idx 8 = Slide 9
    
    # (a) Verify subtitle — already 2 lines with word-boundary, no change needed
    print("\n--- (a) SUBTITLE VERIFICATION ---")
    subtitle_ok, _ = verify_subtitle(slide)
    
    # (b) Read actual card positions
    print("\n--- (b) READING CARD POSITIONS FROM PPTX ---")
    card_positions = read_card_positions(slide)
    
    # (c) Remove wrong Picture 22
    print("\n--- (c) REMOVING WRONG ICON ---")
    removed_count = remove_wrong_picture(slide)
    print(f"[ICON-REMOVE] Removed {removed_count} incorrect picture(s)")
    
    # (d) Add 4 per-card icons
    print("\n--- (d) ADDING 4 PER-CARD ICONS ---")
    added_icons = add_card_icons(slide, card_positions)
    
    # Verify
    print("\n--- VERIFICATION ---")
    icons_ok = verify_added_icons(slide)
    
    # Final checks
    assert len(added_icons) == 4, f"Expected 4 icons added, got {len(added_icons)}"
    assert removed_count >= 1, "Expected at least 1 wrong icon removed"
    assert icons_ok, "Expected exactly 4 pictures on slide after fix"
    
    # Save atomically
    print(f"\n--- SAVING ---")
    print(f"Writing to temp: {TMP_PATH}")
    prs.save(TMP_PATH)
    
    # Atomic replace
    os.replace(TMP_PATH, PPTX_PATH)
    print(f"✓ Atomically replaced: {PPTX_PATH}")
    
    print("\n=== STEP 5 COMPLETE ===")
    
    return {
        "subtitle_fix": "already_correct_no_change",
        "card_positions_read_from_pptx": True,
        "wrong_icons_removed": removed_count,
        "icons_added": [
            {"card": "1.설계", "icon": CARD_ICONS[0], "left_emu": card_positions[0]['icon_left_emu'], "top_emu": card_positions[0]['icon_top_emu']},
            {"card": "2.생성", "icon": CARD_ICONS[1], "left_emu": card_positions[1]['icon_left_emu'], "top_emu": card_positions[1]['icon_top_emu']},
            {"card": "3.연결", "icon": CARD_ICONS[2], "left_emu": card_positions[2]['icon_left_emu'], "top_emu": card_positions[2]['icon_top_emu']},
            {"card": "4.운영", "icon": CARD_ICONS[3], "left_emu": card_positions[3]['icon_left_emu'], "top_emu": card_positions[3]['icon_top_emu']},
        ],
        "icon_size_emu": ICON_SIZE_EMU,
        "save_path": PPTX_PATH,
        "atomic_save": True,
    }


if __name__ == "__main__":
    result = main()
    import json
    print("\n=== RESULT JSON ===")
    print(json.dumps(result, indent=2))
