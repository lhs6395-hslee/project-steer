#!/usr/bin/env python3
"""
Step 5 Validation Script: pipeline_test.pptx 프로그래밍 방식 검증
Acceptance Criteria:
  1. 슬라이드 수 == 1
  2. 표지 제목 텍스트에 '파이프라인 동작 테스트' 포함
  3. 표지 부제 텍스트에 '단일 슬라이드 PPTX 생성 검증' 포함
  4. 날짜 텍스트에 '04/15' 포함
  5. 텍스트 run의 font color가 scheme color로 보존되어 있음
"""
import json
import sys
from pathlib import Path
from pptx import Presentation
from pptx.util import Pt
from lxml import etree

PPTX_PATH = Path(__file__).resolve().parents[2] / "output" / "pipeline_test.pptx"

nsmap = {
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
}

def run_color_info(run_xml):
    """run의 색상 정보를 반환 (scheme color 여부 포함)"""
    rPr = run_xml.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}rPr')
    if rPr is None:
        return {"has_color": False, "is_scheme_color": False, "detail": "no rPr"}
    solidFill = rPr.find('{http://schemas.openxmlformats.org/drawingml/2006/main}solidFill')
    if solidFill is None:
        return {"has_color": False, "is_scheme_color": False, "detail": "no solidFill (inherits theme)"}
    schemeClr = solidFill.find('{http://schemas.openxmlformats.org/drawingml/2006/main}schemeClr')
    srgbClr = solidFill.find('{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr')
    if schemeClr is not None:
        return {"has_color": True, "is_scheme_color": True, "val": schemeClr.get('val'), "detail": f"schemeClr val={schemeClr.get('val')}"}
    elif srgbClr is not None:
        return {"has_color": True, "is_scheme_color": False, "val": srgbClr.get('val'), "detail": f"srgbClr val={srgbClr.get('val')}"}
    return {"has_color": False, "is_scheme_color": False, "detail": "unknown solidFill child"}


def main():
    results = {}
    prs = Presentation(str(PPTX_PATH))

    # ── 1. 슬라이드 수 ──────────────────────────────────────
    slide_count = len(prs.slides)
    results["slide_count"] = {
        "expected": 1,
        "actual": slide_count,
        "pass": slide_count == 1,
    }

    # ── shape 전체 텍스트 수집 ───────────────────────────────
    slide = prs.slides[0]
    all_shapes = []
    for i, shape in enumerate(slide.shapes):
        text = shape.text_frame.text if shape.has_text_frame else ""
        all_shapes.append({"idx": i, "name": shape.name, "text": text})

    results["shapes_snapshot"] = all_shapes

    # ── 2. 표지 제목 ─────────────────────────────────────────
    title_keyword = '파이프라인 동작 테스트'
    title_found = any(title_keyword in s["text"] for s in all_shapes)
    title_shape = next((s for s in all_shapes if title_keyword in s["text"]), None)
    results["title_check"] = {
        "keyword": title_keyword,
        "found": title_found,
        "in_shape": title_shape,
        "pass": title_found,
    }

    # ── 3. 표지 부제 ─────────────────────────────────────────
    subtitle_keyword = '단일 슬라이드 PPTX 생성 검증'
    subtitle_found = any(subtitle_keyword in s["text"] for s in all_shapes)
    subtitle_shape = next((s for s in all_shapes if subtitle_keyword in s["text"]), None)
    results["subtitle_check"] = {
        "keyword": subtitle_keyword,
        "found": subtitle_found,
        "in_shape": subtitle_shape,
        "pass": subtitle_found,
    }

    # ── 4. 날짜 텍스트 ────────────────────────────────────────
    date_keyword = '04/15'
    date_found = any(date_keyword in s["text"] for s in all_shapes)
    date_shape = next((s for s in all_shapes if date_keyword in s["text"]), None)
    results["date_check"] = {
        "keyword": date_keyword,
        "found": date_found,
        "in_shape": date_shape,
        "pass": date_found,
    }

    # ── 5. Font color scheme color 보존 검증 ─────────────────
    scheme_color_details = []
    has_srgb_color = False
    all_scheme_or_inherit = True

    title_shape_idx = title_shape["idx"] if title_shape else None
    subtitle_shape_idx = subtitle_shape["idx"] if subtitle_shape else None

    check_indices = [i for i in [title_shape_idx, subtitle_shape_idx] if i is not None]
    # 날짜 shape 도 포함
    if date_shape:
        check_indices.append(date_shape["idx"])

    for shape in slide.shapes:
        if shape.shape_id - 1 not in check_indices and shape.shape_id not in check_indices:
            # shape.shapes 인덱스 기준 재확인
            pass

    for idx in check_indices:
        shape = slide.shapes[idx]
        if not shape.has_text_frame:
            continue
        tf = shape.text_frame
        for para_i, para in enumerate(tf.paragraphs):
            for run_i, run in enumerate(para.runs):
                info = run_color_info(run._r)
                entry = {
                    "shape_idx": idx,
                    "shape_name": shape.name,
                    "para": para_i,
                    "run": run_i,
                    "run_text": run.text,
                    **info,
                }
                scheme_color_details.append(entry)
                # srgbClr 이 있으면 scheme color 가 아님
                if info["has_color"] and not info["is_scheme_color"]:
                    has_srgb_color = True
                    all_scheme_or_inherit = False

    # scheme color 또는 상속(inherit)인 경우만 PASS
    scheme_color_pass = all_scheme_or_inherit
    results["scheme_color_check"] = {
        "checked_shape_indices": check_indices,
        "details": scheme_color_details,
        "has_srgb_color_override": has_srgb_color,
        "all_scheme_or_inherit": all_scheme_or_inherit,
        "pass": scheme_color_pass,
    }

    # ── 최종 판정 ─────────────────────────────────────────────
    all_pass = all([
        results["slide_count"]["pass"],
        results["title_check"]["pass"],
        results["subtitle_check"]["pass"],
        results["date_check"]["pass"],
        results["scheme_color_check"]["pass"],
    ])
    results["overall_pass"] = all_pass
    results["criteria_summary"] = {
        "C1_slide_count": "PASS" if results["slide_count"]["pass"] else "FAIL",
        "C2_title": "PASS" if results["title_check"]["pass"] else "FAIL",
        "C3_subtitle": "PASS" if results["subtitle_check"]["pass"] else "FAIL",
        "C4_date": "PASS" if results["date_check"]["pass"] else "FAIL",
        "C5_scheme_color": "PASS" if results["scheme_color_check"]["pass"] else "FAIL",
    }

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
