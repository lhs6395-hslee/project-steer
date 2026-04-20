"""
verify_layout.py — PPTX 레이아웃 1:1 스펙 검증 유틸리티

design-spec.md + layout-spec.md 기준으로 각 레이아웃의 shape을
위치·크기·색상·폰트까지 1:1 매핑하여 검증한다.

사용법:
  python modules/pptx/utils/verify_layout.py results/pptx/<file>.pptx
  python modules/pptx/utils/verify_layout.py <file>.pptx --slide 14
  python modules/pptx/utils/verify_layout.py <file>.pptx --layout L13
  python modules/pptx/utils/verify_layout.py <file>.pptx --strict
"""

import re
import sys
import argparse
from pptx import Presentation
from pptx.util import Emu

# ── 상수 ──────────────────────────────────────────────────────────────
SLIDE_W      = 12192000
SLIDE_H      = 6858000
EMU          = 914400   # per inch

# 매칭 허용 편차 (EMU)
TOLERANCE_POS_DEFAULT    = 50000   # 위치 ~0.055"
TOLERANCE_SIZE_DEFAULT   = 60000   # 크기 ~0.066"
TOLERANCE_POS_STRICT     = 15000   # strict 모드
TOLERANCE_SIZE_STRICT    = 15000

# ── 공통 헤더 스펙 (layout-spec.md § "본문 공통 헤더 실측값") ─────────
COMMON_HEADER_SPEC = [
    {
        "id": "subtitle_label",
        "desc": "중제목 TextBox",
        # height는 콘텐츠에 따라 가변 — left/top/width만 검증
        "pos": {"left": 354806, "top": 557906, "width": 2719850},
        "font": {"size_pt": 20.0, "bold": True, "color": "000000", "name_contains": "Freesentation"},
    },
    {
        "id": "subtitle_desc",
        "desc": "설명글 TextBox",
        "pos": {"left": 3763700, "top": 558800, "width": 7551483},
        "font": {"size_pt": 12.0, "bold": False, "name_contains": "Freesentation"},
    },
    {
        "id": "body_title",
        "desc": "요약 제목 TextBox (16pt PRIMARY Bold)",
        "pos": {"left": 457200, "top": 1600200, "width": 11277600, "height": 320040},
        "font": {"size_pt": 16.0, "bold": True, "color": "0043DA", "name_contains": "Freesentation"},
    },
    {
        "id": "body_desc",
        "desc": "요약 설명 TextBox (13pt DARK_GRAY)",
        "pos": {"left": 457200, "top": 1965960, "width": 11277600, "height": 274320},
        "font": {"size_pt": 13.0, "bold": False, "name_contains": "Freesentation"},
    },
]

# ── 레이아웃별 스펙 정의 ───────────────────────────────────────────────
# layout-spec.md의 각 레이아웃 "상세 스펙" 표를 직접 매핑
# pos 값: layout-spec.md 기재 EMU 값 (수정 시 layout-spec.md 기준으로만 변경)
LAYOUT_SPECS = {

    # ── L01 Bento Grid ────────────────────────────────────────────────
    "L01": {
        "name": "Bento Grid",
        "keyword": "L01",
        "shapes": [
            {
                "id": "left_panel",
                "desc": "좌 대형 패널 (RRect)",
                "pos": {"left": 457200, "top": 2628900, "width": 5394960, "height": 3840480},
                "fill_color": "F8F9FA", "border_color": "DCDCDC",
            },
            {
                "id": "right_top_panel",
                "desc": "우상 패널 (RRect)",
                "pos": {"left": 6081308, "top": 2628900, "width": 5650992, "height": 2057400},
                "fill_color": "F8F9FA", "border_color": "DCDCDC",
            },
            {
                "id": "right_bot_panel",
                "desc": "우하 패널 (RRect)",
                "pos": {"left": 6081308, "top": 4960620, "width": 5650992, "height": 1508760},
                "fill_color": "F8F9FA", "border_color": "DCDCDC",
            },
            {
                "id": "left_title",
                "desc": "좌 패널 제목 TextBox",
                "pos": {"left": 637200, "top": 2859982, "width": 5034960, "height": 320040},
                "font": {"size_pt": 14.0, "bold": True, "color": "0043DA", "name_contains": "Freesentation"},
            },
            {
                "id": "left_content",
                "desc": "좌 패널 내용 TextBox",
                "pos": {"left": 637200, "top": 3288022, "width": 5034960, "height": 1554480},
                "font": {"size_pt": 13.0, "bold": False, "name_contains": "Freesentation"},
            },
            {
                "id": "right_top_title",
                "desc": "우상 제목 TextBox",
                "pos": {"left": 6261308, "top": 2706067, "width": 5290992, "height": 320040},
                "font": {"size_pt": 14.0, "bold": True, "color": "0043DA", "name_contains": "Freesentation"},
            },
            {
                "id": "right_bot_title",
                "desc": "우하 제목 TextBox",
                "pos": {"left": 6261308, "top": 5006988, "width": 5290992, "height": 320040},
                "font": {"size_pt": 14.0, "bold": True, "color": "0043DA", "name_contains": "Freesentation"},
            },
        ],
    },

    # ── L03 Grid 2×2 ─────────────────────────────────────────────────
    "L03": {
        "name": "Grid 2×2",
        "keyword": "L03",
        "shapes": [
            {
                "id": "card_lt",
                "desc": "좌상 카드 (RRect)",
                "pos": {"left": 564093, "top": 2628900, "width": 5394960, "height": 1828800},
                "fill_color": "F8F9FA", "border_color": "DCDCDC",
            },
            {
                "id": "card_rt",
                "desc": "우상 카드 (RRect)",
                "pos": {"left": 6233190, "top": 2628900, "width": 5394960, "height": 1828800},
                "fill_color": "F8F9FA", "border_color": "DCDCDC",
            },
            {
                "id": "card_lb",
                "desc": "좌하 카드 (RRect)",
                "pos": {"left": 564093, "top": 4732020, "width": 5394960, "height": 1737360},
                "fill_color": "F8F9FA", "border_color": "DCDCDC",
            },
            {
                "id": "card_rb",
                "desc": "우하 카드 (RRect)",
                "pos": {"left": 6233190, "top": 4732020, "width": 5394960, "height": 1737360},
                "fill_color": "F8F9FA", "border_color": "DCDCDC",
            },
            {
                "id": "card_lt_title",
                "desc": "좌상 카드 제목",
                "pos": {"left": 744093, "top": 2691622, "width": 5034960, "height": 365760},
                "font": {"size_pt": 14.0, "bold": True, "color": "0043DA", "name_contains": "Freesentation"},
            },
            {
                "id": "card_lt_content",
                "desc": "좌상 카드 내용",
                "pos": {"left": 744093, "top": 3165382, "width": 5034960, "height": 1097280},
                "font": {"size_pt": 13.0, "bold": False, "name_contains": "Freesentation"},
            },
        ],
    },

    # ── L13 Pros & Cons ───────────────────────────────────────────────
    "L13": {
        "name": "Pros & Cons",
        "keyword": "L13",
        "shapes": [
            {
                "id": "pros_panel",
                "desc": "Pros 패널 (RRect)",
                "pos": {"left": 457200, "top": 2423160, "width": 5486400, "height": 3657600},
                "fill_color": "B2D9CD", "border_color": "4CB88F",
                "corner_radius_adj": 16667,
                "shape_type": "rrect",
            },
            {
                "id": "pros_title",
                "desc": "Pros 제목 TextBox (left=아이콘 위치 0.697\")",
                "pos": {"left": 637160, "top": 2603120, "width": 5124640, "height": 274320},
                "font": {"size_pt": 14.0, "bold": True, "color": "212121", "name_contains": "Freesentation"},
                "text_contains": "Pros",
            },
            {
                "id": "pros_content",
                "desc": "Pros 내용 TextBox",
                "pos": {"left": 637160, "top": 2968800, "width": 5124480, "height": 2930160},
                "font": {"size_pt": 13.0, "name_contains": "Freesentation"},
            },
            {
                "id": "cons_panel",
                "desc": "Cons 패널 (RRect)",
                "pos": {"left": 6291360, "top": 2423160, "width": 5486400, "height": 3657600},
                "fill_color": "F6C0A8", "border_color": "EE8150",
                "corner_radius_adj": 16667,
                "shape_type": "rrect",
            },
            {
                "id": "cons_title",
                "desc": "Cons 제목 TextBox (left=아이콘 위치 7.077\")",
                "pos": {"left": 6471320, "top": 2603120, "width": 5124640, "height": 274320},
                "font": {"size_pt": 14.0, "bold": True, "color": "212121", "name_contains": "Freesentation"},
                "text_contains": "Cons",
            },
            {
                "id": "cons_content",
                "desc": "Cons 내용 TextBox",
                "pos": {"left": 6471320, "top": 2968800, "width": 5124480, "height": 2930160},
                "font": {"size_pt": 13.0, "name_contains": "Freesentation"},
            },
            {
                "id": "verdict_bar",
                "desc": "종합 판단 바 (RRect)",
                "pos": {"left": 457200, "top": 6172200, "width": 11320560, "height": 457200},
                "fill_color": "0043DA",
            },
            {
                "id": "verdict_text",
                "desc": "종합 판단 텍스트",
                "pos": {"left": 637160, "top": 6217920, "width": 10960200, "height": 365760},
                "font": {"size_pt": 14.0, "bold": True, "color": "FFFFFF", "name_contains": "Freesentation"},
                "text_contains": "판단",
            },
        ],
    },

    # ── L14 Do / Don't ────────────────────────────────────────────────
    "L14": {
        "name": "Do / Don't",
        "keyword": "L14",
        "shapes": [
            {
                "id": "do_panel",
                "desc": "DO 패널 (RRect)",
                "pos": {"left": 457200, "top": 2423160, "width": 5486400, "height": 3657600},
                "fill_color": "B2D9CD", "border_color": "4CB88F",
            },
            {
                "id": "do_title",
                "desc": "DO 제목 TextBox (left=0.697\")",
                "pos": {"left": 637160, "top": 2603120, "width": 5124640, "height": 274320},
                "font": {"size_pt": 14.0, "bold": True, "color": "212121", "name_contains": "Freesentation"},
                "text_contains": "DO",
            },
            {
                "id": "do_content",
                "desc": "DO 내용 TextBox",
                "pos": {"left": 637160, "top": 2968800, "width": 5124480, "height": 2930160},
                "font": {"size_pt": 13.0, "name_contains": "Freesentation"},
            },
            {
                "id": "dont_panel",
                "desc": "DON'T 패널 (RRect)",
                "pos": {"left": 6291360, "top": 2423160, "width": 5486400, "height": 3657600},
                "fill_color": "C62828",
            },
            {
                "id": "dont_title",
                "desc": "DON'T 제목 TextBox (left=7.077\")",
                "pos": {"left": 6471320, "top": 2603120, "width": 5124640, "height": 274320},
                "font": {"size_pt": 14.0, "bold": True, "color": "FFFFFF", "name_contains": "Freesentation"},
                "text_contains": "DON",
            },
            {
                "id": "dont_content",
                "desc": "DON'T 내용 TextBox",
                "pos": {"left": 6471320, "top": 2968800, "width": 5124480, "height": 2930160},
                "font": {"size_pt": 13.0, "color": "FFFFFF", "name_contains": "Freesentation"},
            },
            {
                "id": "status_bar",
                "desc": "준수 현황 바 (RRect, 선택적)",
                "pos": {"left": 457200, "top": 6172200, "width": 11320560, "height": 457200},
                "fill_color_any": ["F8F9FA", "0043DA"],  # 내용에 따라 둘 중 하나
                "optional": True,
            },
        ],
    },

    # ── L15 SWOT Matrix ───────────────────────────────────────────────
    "L15": {
        "name": "SWOT Matrix",
        "keyword": "L15",
        "shapes": [
            {
                "id": "label_internal",
                "desc": "\"내부 요인\" 축 레이블",
                "pos": {"left": 457200, "top": 2240280, "width": 5669280, "height": 182880},
                "font": {"size_pt": 11.0, "bold": False, "name_contains": "Freesentation"},
                "text_contains": "내부",
            },
            {
                "id": "label_external",
                "desc": "\"외부 요인\" 축 레이블",
                "pos": {"left": 6217920, "top": 2240280, "width": 5669280, "height": 182880},
                "font": {"size_pt": 11.0, "bold": False, "name_contains": "Freesentation"},
                "text_contains": "외부",
            },
            {
                "id": "quadrant_s",
                "desc": "Strengths 사분면 (좌상, RRect)",
                "pos": {"left": 457200, "top": 2423160, "width": 5669280, "height": 1737360},
                "border_color": "DCDCDC",
                "shape_type": "rrect",
            },
            {
                "id": "quadrant_o",
                "desc": "Opportunities 사분면 (우상, RRect)",
                "pos": {"left": 6217920, "top": 2423160, "width": 5669280, "height": 1737360},
                "border_color": "DCDCDC",
                "shape_type": "rrect",
            },
            {
                "id": "quadrant_w",
                "desc": "Weaknesses 사분면 (좌하, RRect)",
                "pos": {"left": 457200, "top": 4251960, "width": 5669280, "height": 1828800},
                "border_color": "DCDCDC",
                "shape_type": "rrect",
            },
            {
                "id": "quadrant_t",
                "desc": "Threats 사분면 (우하, RRect)",
                "pos": {"left": 6217920, "top": 4251960, "width": 5669280, "height": 1828800},
                "border_color": "DCDCDC",
                "shape_type": "rrect",
            },
            {
                "id": "strategy_bar",
                "desc": "전략 방향 바 (RRect)",
                "pos": {"left": 457200, "top": 6172200, "width": 11430000, "height": 457200},
                "fill_color": "0043DA",
            },
            {
                "id": "strategy_text",
                "desc": "전략 방향 텍스트",
                "pos": {"left": 637160, "top": 6217920, "width": 11069640, "height": 365760},
                "font": {"size_pt": 14.0, "bold": True, "color": "FFFFFF", "name_contains": "Freesentation"},
            },
        ],
    },

    # ── L12 Before/After ─────────────────────────────────────────────
    "L12": {
        "name": "Before/After",
        "keyword": "L12",
        "shapes": [
            {
                "id": "before_panel",
                "desc": "BEFORE 패널",
                "pos": {"left": 457200, "top": 2789820, "width": 5394960, "height": 3885660},
                "fill_color": "F8F9FA", "border_color": "DCDCDC",
            },
            {
                "id": "after_panel",
                "desc": "AFTER 패널",
                "pos": {"left": 6248160, "top": 2789820, "width": 5486400, "height": 3885660},
                "fill_color": "F8F9FA", "border_color": "DCDCDC",
            },
        ],
    },
}

# ── XML 파싱 헬퍼 ─────────────────────────────────────────────────────
def _get_srgb_colors(shape) -> list[str]:
    """shape XML에서 srgbClr val 목록 반환 (대문자)"""
    xml = shape._element.xml
    return [c.upper() for c in re.findall(r'srgbClr val="([0-9A-Fa-f]{6})"', xml)]

def _get_fill_color(shape) -> str | None:
    """solidFill 첫 번째 srgbClr 반환"""
    xml = shape._element.xml
    # solidFill 블록에서 첫 번째 srgbClr
    block = re.search(r'<a:solidFill>(.*?)</a:solidFill>', xml, re.DOTALL)
    if block:
        m = re.search(r'srgbClr val="([0-9A-Fa-f]{6})"', block.group(1))
        if m:
            return m.group(1).upper()
    return None

def _get_border_color(shape) -> str | None:
    """ln/solidFill/srgbClr 반환"""
    xml = shape._element.xml
    ln = re.search(r'<a:ln[^>]*>(.*?)</a:ln>', xml, re.DOTALL)
    if ln:
        m = re.search(r'srgbClr val="([0-9A-Fa-f]{6})"', ln.group(1))
        if m:
            return m.group(1).upper()
    return None

def _get_corner_radius_adj(shape) -> int | None:
    """avLst/gd[@name='adj'] fmla 값 반환"""
    xml = shape._element.xml
    m = re.search(r'<a:gd name="adj" fmla="val (\d+)"', xml)
    return int(m.group(1)) if m else None

def _get_first_run_font(shape) -> dict:
    """첫 번째 단락의 첫 번째 run에서 폰트 정보 추출"""
    result = {}
    if not shape.has_text_frame:
        return result
    for para in shape.text_frame.paragraphs:
        for run in para.runs:
            f = run.font
            result["name"] = f.name or ""
            result["size_pt"] = round(f.size.pt, 1) if f.size else None
            result["bold"] = f.bold
            try:
                result["color"] = str(f.color.rgb).upper() if f.color and f.color.type else None
            except Exception:
                result["color"] = None
            return result
    return result

def _get_fill_type_name(shape) -> str:
    try:
        ft = shape.fill.type
        return ft.name if ft else "NONE"
    except Exception:
        return "UNKNOWN"

# ── 단일 shape 검증 ────────────────────────────────────────────────────
def _check_shape(actual, spec_item, tol_pos, tol_size) -> list[str]:
    """shape을 spec_item과 비교, 위반 목록 반환"""
    issues = []

    # 위치·크기 (pos dict에 명시된 키만 검증 — height 생략 가능)
    ep = spec_item["pos"]
    for key, spec_val in ep.items():
        actual_val = getattr(actual, key, None)
        if actual_val is None:
            continue
        diff = abs(actual_val - spec_val)
        tol = tol_pos if key in ("left", "top") else tol_size
        if diff > tol:
            actual_in = round(actual_val / EMU, 3)
            spec_in   = round(spec_val / EMU, 3)
            issues.append(f"{key}: {actual_val}({actual_in}\") ≠ spec {spec_val}({spec_in}\")  Δ={diff}")

    # 채우기 색상
    if "fill_color" in spec_item:
        fc = _get_fill_color(actual)
        spec_fc = spec_item["fill_color"].upper()
        if fc != spec_fc:
            issues.append(f"fill_color: {fc} ≠ spec {spec_fc}")

    # 채우기 색상 (복수 허용)
    if "fill_color_any" in spec_item:
        fc = _get_fill_color(actual)
        allowed = [c.upper() for c in spec_item["fill_color_any"]]
        if fc not in allowed:
            issues.append(f"fill_color: {fc} ≠ any of {allowed}")

    # 보더 색상
    if "border_color" in spec_item:
        bc = _get_border_color(actual)
        spec_bc = spec_item["border_color"].upper()
        if bc != spec_bc:
            issues.append(f"border_color: {bc} ≠ spec {spec_bc}")

    # corner radius
    if "corner_radius_adj" in spec_item:
        adj = _get_corner_radius_adj(actual)
        spec_adj = spec_item["corner_radius_adj"]
        if adj is None or abs(adj - spec_adj) > 2000:
            issues.append(f"corner_radius adj: {adj} ≠ spec {spec_adj}")

    # 폰트
    if "font" in spec_item and actual.has_text_frame:
        fspec = spec_item["font"]
        frun  = _get_first_run_font(actual)
        if frun:
            if "name_contains" in fspec:
                fname = frun.get("name") or ""
                if fspec["name_contains"].lower() not in fname.lower():
                    issues.append(f"font.name: \"{fname}\" does not contain \"{fspec['name_contains']}\"")
            if "size_pt" in fspec and frun.get("size_pt") is not None:
                if abs(frun["size_pt"] - fspec["size_pt"]) > 0.5:
                    issues.append(f"font.size: {frun['size_pt']}pt ≠ spec {fspec['size_pt']}pt")
            if "bold" in fspec and frun.get("bold") is not None:
                if frun["bold"] != fspec["bold"]:
                    issues.append(f"font.bold: {frun['bold']} ≠ spec {fspec['bold']}")
            if "color" in fspec and frun.get("color") is not None:
                if frun["color"].upper() != fspec["color"].upper():
                    issues.append(f"font.color: {frun['color']} ≠ spec {fspec['color'].upper()}")

    # 텍스트 내용 포함
    if "text_contains" in spec_item and actual.has_text_frame:
        t = actual.text_frame.text
        if spec_item["text_contains"] not in t:
            issues.append(f"text: \"{t[:30]}\" 에 \"{spec_item['text_contains']}\" 없음")

    return issues

# ── shape 매칭 (위치 기반, 중복 방지) ────────────────────────────────
def _find_shape(slide, spec_pos: dict, tol_pos: int, tol_size: int,
                text_hint: str | None = None,
                shape_type_filter: str | None = None,
                used_ids: set | None = None):
    """
    spec_pos에 가장 가까운 shape 반환.
    - text_hint가 있으면 텍스트 포함 shape 우선
    - shape_type_filter: 'rrect'(AutoShape), 'textbox', 'pic'
    - used_ids: 이미 매칭된 shape id 집합 (중복 방지)
    """
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    TYPE_MAP = {
        "rrect":   MSO_SHAPE_TYPE.AUTO_SHAPE,
        "textbox": MSO_SHAPE_TYPE.TEXT_BOX,
        "pic":     MSO_SHAPE_TYPE.PICTURE,
    }

    best = None
    best_dist = float("inf")

    for shape in slide.shapes:
        # 중복 방지
        # 안정 식별자: 위치 튜플 (lxml proxy는 매 iteration마다 재생성되어 id() 불안정)
        shape_key = (shape.left, shape.top, shape.width, shape.height)
        if used_ids is not None and shape_key in used_ids:
            continue
        # 타입 필터
        if shape_type_filter and shape_type_filter in TYPE_MAP:
            if shape.shape_type != TYPE_MAP[shape_type_filter]:
                continue
        # 위치 거리
        dl = abs(shape.left - spec_pos["left"])
        dt = abs(shape.top  - spec_pos["top"])
        if dl > tol_pos * 4 or dt > tol_pos * 4:
            continue
        dist = dl + dt
        # text_hint 보너스
        if text_hint and shape.has_text_frame and text_hint in shape.text_frame.text:
            dist = max(0, dist - tol_pos * 2)
        if dist < best_dist:
            best_dist = dist
            best = shape

    if best is not None and best_dist <= (tol_pos + tol_size) * 4:
        return best
    return None

# ── 슬라이드 검증 ─────────────────────────────────────────────────────
def _get_slide_label(slide) -> str:
    for s in slide.shapes:
        if s.has_text_frame and 0.55 < s.top / EMU < 0.72:
            t = s.text_frame.text.strip()
            if t:
                return t[:50]
    return ""

def _detect_layout(label: str) -> str | None:
    """레이블에서 레이아웃 코드 추출 (예: 'L13. Pros...' → 'L13')"""
    m = re.search(r'\bL(\d+)\b', label)
    return f"L{m.group(1)}" if m else None

def check_slide(slide_idx: int, slide, tol_pos: int, tol_size: int,
                check_header: bool = True) -> dict:
    result = {
        "slide_idx": slide_idx,
        "label": _get_slide_label(slide),
        "layout_code": None,
        "checks": [],   # list of {id, desc, found, issues, optional}
        "pass": True,
    }
    label = result["label"]
    layout_code = _detect_layout(label)
    result["layout_code"] = layout_code

    # 공통 헤더 검증
    if check_header:
        for hspec in COMMON_HEADER_SPEC:
            text_hint = None
            if "text_contains" in hspec:
                text_hint = hspec["text_contains"]
            shape = _find_shape(slide, hspec["pos"], tol_pos, tol_size, text_hint)
            check = {
                "id": f"header.{hspec['id']}",
                "desc": f"[공통헤더] {hspec['desc']}",
                "optional": False,
                "found": shape is not None,
                "issues": [],
            }
            if shape:
                check["issues"] = _check_shape(shape, hspec, tol_pos, tol_size)
            else:
                check["issues"] = ["shape을 찾을 수 없음"]
            result["checks"].append(check)

    # 레이아웃별 스펙 검증 (used_ids로 중복 매칭 방지)
    used_ids: set = set()
    if layout_code and layout_code in LAYOUT_SPECS:
        spec = LAYOUT_SPECS[layout_code]
        for sspec in spec["shapes"]:
            text_hint   = sspec.get("text_contains")
            type_filter = sspec.get("shape_type")
            shape = _find_shape(slide, sspec["pos"], tol_pos, tol_size,
                                text_hint, type_filter, used_ids)
            if shape:
                used_ids.add((shape.left, shape.top, shape.width, shape.height))
            optional = sspec.get("optional", False)
            check = {
                "id": sspec["id"],
                "desc": sspec["desc"],
                "optional": optional,
                "found": shape is not None,
                "issues": [],
            }
            if shape:
                check["issues"] = _check_shape(shape, sspec, tol_pos, tol_size)
            elif not optional:
                check["issues"] = ["shape을 찾을 수 없음 (MISSING)"]
            result["checks"].append(check)
    elif layout_code:
        result["checks"].append({
            "id": "no_spec",
            "desc": f"[{layout_code}] 스펙 미정의 — 공통 헤더만 검증됨",
            "optional": True,
            "found": True,
            "issues": [],
        })

    # 종합 판정
    has_fail = any(
        not c["found"] or (c["issues"] and not c["optional"])
        for c in result["checks"]
        if not c["optional"]
    )
    result["pass"] = not has_fail
    return result

# ── 출력 ──────────────────────────────────────────────────────────────
def _print_result(r: dict, verbose: bool = False):
    layout_code = r["layout_code"] or "?"
    label_short = r["label"][:35] if r["label"] else "(비본문)"
    icon = "✅" if r["pass"] else "❌"
    print(f"\n[{r['slide_idx']:02d}] {label_short}  {icon}")

    # 실패·미발견 항목만 출력 (verbose면 전체)
    for c in r["checks"]:
        optional_tag = " (선택)" if c["optional"] else ""
        if not c["found"]:
            print(f"    ❌  MISSING  {c['desc']}{optional_tag}")
        elif c["issues"]:
            status = "⚠️ " if c["optional"] else "❌"
            print(f"    {status} FAIL  {c['desc']}{optional_tag}")
            for issue in c["issues"]:
                print(f"           • {issue}")
        elif verbose:
            print(f"    ✅  PASS  {c['desc']}{optional_tag}")

# ── 메인 ──────────────────────────────────────────────────────────────
def run(pptx_path: str, target_slide: int | None = None,
        target_layout: str | None = None,
        strict: bool = False,
        verbose: bool = False,
        no_header: bool = False) -> bool:

    tol_pos  = TOLERANCE_POS_STRICT  if strict else TOLERANCE_POS_DEFAULT
    tol_size = TOLERANCE_SIZE_STRICT if strict else TOLERANCE_SIZE_DEFAULT

    prs = Presentation(pptx_path)
    total_slides = len(prs.slides)

    # 대상 슬라이드 결정
    if target_slide is not None:
        indices = [target_slide]
    elif target_layout is not None:
        # 레이아웃 코드로 슬라이드 자동 탐색
        indices = []
        for i, slide in enumerate(prs.slides):
            lbl = _get_slide_label(slide)
            if target_layout.upper() in lbl.upper():
                indices.append(i)
        if not indices:
            print(f"[경고] '{target_layout}' 레이아웃 슬라이드를 찾을 수 없음")
            return False
    else:
        indices = range(total_slides)

    results = []
    for idx in indices:
        slide = prs.slides[idx]
        label = _get_slide_label(slide)
        # 비본문 슬라이드 건너뜀
        if not label or any(kw in label for kw in ("CONTENTS", "Thank You", "WiseN")):
            continue
        r = check_slide(idx, slide, tol_pos, tol_size, check_header=not no_header)
        results.append(r)
        _print_result(r, verbose=verbose)

    # 요약
    passed  = sum(1 for r in results if r["pass"])
    failed  = sum(1 for r in results if not r["pass"])
    total_checks = sum(len(r["checks"]) for r in results)
    total_issues = sum(
        sum(1 for c in r["checks"] if c["issues"] and not c["optional"])
        for r in results
    )
    total_missing = sum(
        sum(1 for c in r["checks"] if not c["found"] and not c["optional"])
        for r in results
    )

    print(f"\n{'─'*60}")
    mode_str = "strict" if strict else "normal"
    print(f"검증 결과 ({mode_str}, tol_pos={tol_pos//1000}K EMU)")
    print(f"  슬라이드: {passed} PASS / {failed} FAIL  (총 {len(results)})")
    print(f"  항목:     {total_checks}개 중 {total_issues}개 위반, {total_missing}개 누락")
    print(f"  스펙 정의: {sorted(LAYOUT_SPECS.keys())}")

    return failed == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PPTX 레이아웃 1:1 스펙 검증")
    parser.add_argument("pptx", help="PPTX 파일 경로")
    parser.add_argument("--slide", type=int, default=None, help="특정 슬라이드 인덱스 (0-based)")
    parser.add_argument("--layout", type=str, default=None, help="레이아웃 코드 (예: L13)")
    parser.add_argument("--strict", action="store_true", help="엄격 모드 (허용 편차 15K EMU)")
    parser.add_argument("--verbose", "-v", action="store_true", help="PASS 항목도 출력")
    parser.add_argument("--no-header", action="store_true", help="공통 헤더 검증 건너뜀")
    args = parser.parse_args()

    ok = run(args.pptx, args.slide, args.layout, args.strict, args.verbose, args.no_header)
    sys.exit(0 if ok else 1)
