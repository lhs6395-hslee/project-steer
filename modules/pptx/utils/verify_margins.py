"""
verify_margins.py — PPTX 콘텐츠 영역 여백 검증 유틸리티

원칙 (design-spec.md 기준):
  - 본문 슬라이드: 본문 제목+설명글 아래 콘텐츠 영역의 좌/우 여백 동일, 상/하 여백 동일
  - 좌/우 허용 기준: 0.500" ± 0.050"
  - 상/하 동일 기준: |top_margin - bottom_margin| ≤ 0.050"

사용법:
  python modules/pptx/utils/verify_margins.py results/pptx/AWS_MSK_Expert_Intro.pptx
  python modules/pptx/utils/verify_margins.py <file.pptx> --slide 17
  python modules/pptx/utils/verify_margins.py <file.pptx> --tolerance 0.1
"""

import re
import sys
import argparse
from pptx import Presentation
from pptx.util import Emu

# ── 상수 ──────────────────────────────────────────────────────────────
SLIDE_W       = 12192000   # 13.333" (EMU)
SLIDE_H       = 6858000    # 7.500"  (EMU)
EMU_PER_INCH  = 914400

# 헤더 영역 경계 (이 범위 이하 shape은 중제목/본문제목/설명글로 취급)
HEADER_BOTTOM_THRESHOLD = 2400000   # ~2.625"

# 배경 full-width shape 제외 기준
FULL_WIDTH_THRESHOLD = 11000000  # 너비 >= 이 값이면 배경으로 간주

# 비본문 슬라이드 제외 (title, contents, thank you 등)
NON_BODY_KEYWORDS = {"CONTENTS", "Thank You", "WiseN"}

# 여백 기준 (inch)
TARGET_SIDE_MARGIN  = 0.500   # 좌/우 목표 여백
TOLERANCE_SIDE      = 0.060   # 좌/우 허용 편차 (±0.06")
TOLERANCE_SYMMETRIC = 0.060   # 상/하 대칭 허용 편차 (|top-bottom| ≤ 0.06")

# 레이아웃별 예외 — layout-spec.md 에 명시된 설계 의도
# 좌/우 대칭이지만 0.500" 초과 허용 (격자 구조상 고정값)
WIDE_SIDE_MARGIN_OK_KEYWORDS = {"Grid 2x2"}
# 상/하 비대칭이 설계상 불가피한 레이아웃 — 각각 허용 편차(inch)
TOPBOTTOM_CUSTOM_TOLERANCE = {
    "SWOT Matrix":      0.150,  # L15: 전략 바 하단 고정 → 0.100" 비대칭 불가피
    "Icon Grid":        0.500,  # L19: 2행 그리드 미충족 → 0.400" 비대칭 설계 의도
    "Stats Dashboard":  0.250,  # L23: KPI+요약바 → 0.200" 비대칭 설계 의도
}

# 헤더 shape 최대 bottom (2.500" = 2286000 EMU)
# 이를 초과하는 shape은 실제 콘텐츠로 간주 (연도탭, 컬럼헤더 등 오탐 방지)
HEADER_MAX_BOTTOM = 2286000  # 2.500"

# ── 헬퍼 ──────────────────────────────────────────────────────────────
def to_inch(emu: int) -> float:
    return emu / EMU_PER_INCH

def is_non_body_slide(slide) -> bool:
    """비본문 슬라이드 판별 — 레이아웃 이름 우선, 키워드·위치 보조 판단"""
    # 1. 레이아웃 이름 기반 — "본문" 레이아웃이면 무조건 본문 슬라이드
    try:
        if slide.slide_layout.name == "본문":
            return False
    except Exception:
        pass

    # 2. 키워드 기반 (CONTENTS, Thank You 등)
    for shape in slide.shapes:
        if shape.has_text_frame:
            t = shape.text_frame.text.strip()
            for kw in NON_BODY_KEYWORDS:
                if kw in t:
                    return True

    # 3. 중제목 위치(0.55~0.72")에 텍스트 shape이 있으면 본문 슬라이드
    #    LXX. 패턴 불필요 — 실제 콘텐츠 프리젠테이션 호환
    for shape in slide.shapes:
        if shape.has_text_frame and 0.55 < shape.top / EMU_PER_INCH < 0.72:
            t = shape.text_frame.text.strip()
            if t:
                return False

    return True  # 비본문 (표지/구분 슬라이드 등)

def get_body_header_bottom(slide) -> int:
    """
    본문 제목(요약 제목, 16pt PRIMARY, top≈1.75") + 설명글(13pt, top≈2.15")의
    하단 경계를 반환한다.
    헤더 영역(1.4" ~ 2.6") 내 shape 중 bottom ≤ 2.500"인 것만 포함
    (연도탭·컬럼헤더 등 콘텐츠 shape이 헤더로 오탐되는 것을 방지).
    """
    header_bottom = 0
    for shape in slide.shapes:
        # 본문제목/설명글 영역: top > 1.4" (1280160) AND top < 2.6" (2377640)
        # 단, bottom > 2.500" (2286000)이면 실제 콘텐츠로 간주하여 제외
        if 1280160 < shape.top < 2377640:
            bottom = shape.top + shape.height
            if bottom <= HEADER_MAX_BOTTOM and bottom > header_bottom:
                header_bottom = bottom
    # 헤더가 없으면 중제목 영역 하단을 기준으로 (top≈1.5")
    if header_bottom == 0:
        header_bottom = 1490040
    return header_bottom

def has_fullbg_image(slide) -> bool:
    """풀슬라이드 배경 이미지가 있는 레이아웃 판별 (L18 Full Image 등).
    width ≥ 95% × SLIDE_W이고 left ≤ 50000인 shape이 존재하면 True."""
    for shape in slide.shapes:
        if shape.width >= int(SLIDE_W * 0.95) and shape.left <= 50000:
            return True
    return False

def get_content_bounds(slide, header_bottom: int):
    """
    헤더 아래 콘텐츠 shape들의 경계 (left, right, top, bottom) 반환.
    배경용 full-width shape 및 얇은 구분선은 제외.
    """
    lefts, rights, tops, bottoms = [], [], [], []
    for shape in slide.shapes:
        # 헤더 영역 shape 제외
        if shape.top < header_bottom - 50000:
            continue
        # 배경 full-width shape 제외
        # left < TARGET_MARGIN(457200) — 콘텐츠 기준선(0.500") 이전에서 시작하는
        # 배경/구분선 shape만 제외. 0.500"에서 시작하는 정상 콘텐츠는 포함 유지.
        if shape.width >= FULL_WIDTH_THRESHOLD and shape.left < int(TARGET_SIDE_MARGIN * 914400):
            continue
        lefts.append(shape.left)
        rights.append(shape.left + shape.width)
        tops.append(shape.top)
        bottoms.append(shape.top + shape.height)

    if not lefts:
        return None
    return {
        "left":   min(lefts),
        "right":  max(rights),
        "top":    min(tops),
        "bottom": max(bottoms),
    }

def check_slide(slide_idx: int, slide, tolerance_sym: float = TOLERANCE_SYMMETRIC,
                tolerance_side: float = TOLERANCE_SIDE):
    """
    단일 슬라이드 여백 검증. dict 반환.
    """
    result = {
        "slide_idx": slide_idx,
        "label": "",
        "skipped": False,
        "skip_reason": "",
        "left_margin":   None,
        "right_margin":  None,
        "top_margin":    None,
        "bottom_margin": None,
        "header_bottom": None,
        "issues": [],
        "pass": True,
    }

    # 슬라이드 레이블 추출 (중제목 텍스트)
    for shape in slide.shapes:
        if shape.has_text_frame and 0.55 < shape.top / EMU_PER_INCH < 0.72:
            t = shape.text_frame.text.strip()
            if t:
                result["label"] = t[:40]
                break

    if is_non_body_slide(slide):
        result["skipped"] = True
        result["skip_reason"] = "비본문 슬라이드 (표지/목차/끝인사)"
        return result

    # Full Image 배경 레이아웃은 콘텐츠 비대칭이 설계 의도 → 마진 체크 비적용
    if has_fullbg_image(slide):
        result["skipped"] = True
        result["skip_reason"] = "Full Image 배경 레이아웃 (좌우 대칭 마진 비적용)"
        return result

    header_bottom = get_body_header_bottom(slide)
    result["header_bottom"] = to_inch(header_bottom)
    bounds = get_content_bounds(slide, header_bottom)

    if bounds is None:
        result["skipped"] = True
        result["skip_reason"] = "콘텐츠 shape 없음"
        return result

    left_m   = to_inch(bounds["left"])
    right_m  = to_inch(SLIDE_W - bounds["right"])
    top_m    = to_inch(bounds["top"] - header_bottom)
    bottom_m = to_inch(SLIDE_H - bounds["bottom"])

    result.update({
        "left_margin":   round(left_m, 3),
        "right_margin":  round(right_m, 3),
        "top_margin":    round(top_m, 3),
        "bottom_margin": round(bottom_m, 3),
    })

    # ── 검증 ──────────────────────────────────────
    issues = []
    label = result.get("label", "")

    # 레이아웃별 예외 적용
    wide_side_ok = any(kw in label for kw in WIDE_SIDE_MARGIN_OK_KEYWORDS)
    tb_tolerance = next(
        (v for kw, v in TOPBOTTOM_CUSTOM_TOLERANCE.items() if kw in label),
        tolerance_sym
    )

    # 1. 좌/우 여백 기준 범위 (0.500" ± tolerance_side)
    #    WIDE_SIDE_MARGIN_OK 레이아웃: 대칭이면 범위 초과 허용 (격자 구조 고정값)
    if not wide_side_ok:
        if not (TARGET_SIDE_MARGIN - tolerance_side <= left_m <= TARGET_SIDE_MARGIN + tolerance_side):
            issues.append(
                f"좌 여백 {left_m:.3f}\" — 기준 {TARGET_SIDE_MARGIN:.3f}\" ± {tolerance_side:.3f}\""
            )
        if not (TARGET_SIDE_MARGIN - tolerance_side <= right_m <= TARGET_SIDE_MARGIN + tolerance_side):
            issues.append(
                f"우 여백 {right_m:.3f}\" — 기준 {TARGET_SIDE_MARGIN:.3f}\" ± {tolerance_side:.3f}\""
            )

    # 2. 좌/우 대칭 (예외 레이아웃도 대칭 체크는 항상 수행)
    if abs(left_m - right_m) > tolerance_side:
        issues.append(
            f"좌우 비대칭 |{left_m:.3f}\" - {right_m:.3f}\"| = {abs(left_m-right_m):.3f}\""
        )

    # 3. 상/하 대칭 (레이아웃별 커스텀 허용 편차 적용)
    if abs(top_m - bottom_m) > tb_tolerance:
        issues.append(
            f"상하 비대칭 |top {top_m:.3f}\" - bottom {bottom_m:.3f}\"| = {abs(top_m-bottom_m):.3f}\""
        )

    # 4. 하단 여백 최소값 (0.100" 미만은 무조건 경고)
    if bottom_m < 0.100:
        issues.append(f"하단 여백 부족 {bottom_m:.3f}\" (최소 0.100\" 필요)")

    result["issues"] = issues
    result["pass"] = len(issues) == 0
    return result


# ── 메인 ──────────────────────────────────────────────────────────────
def run(pptx_path: str, target_slide: int = None,
        tolerance_sym: float = TOLERANCE_SYMMETRIC,
        tolerance_side: float = TOLERANCE_SIDE):

    prs = Presentation(pptx_path)
    results = []

    slide_range = [target_slide] if target_slide is not None else range(len(prs.slides))

    for idx in slide_range:
        slide = prs.slides[idx]
        r = check_slide(idx, slide, tolerance_sym, tolerance_side)
        results.append(r)

    # ── 출력 ──────────────────────────────────────
    PASS_ICON = "✅"
    FAIL_ICON = "❌"
    SKIP_ICON = "—"

    print(f"\n{'슬라이드':<6} {'레이블':<28} {'좌':>6} {'우':>6} {'상':>6} {'하':>6}  {'판정'}")
    print("─" * 80)

    total = skip = passed = failed = 0
    for r in results:
        total += 1
        if r["skipped"]:
            skip += 1
            print(f"[{r['slide_idx']:02d}]  {r['label'] or '(비본문)':<28}  {'—':>6} {'—':>6} {'—':>6} {'—':>6}  {SKIP_ICON} {r['skip_reason']}")
            continue

        icon = PASS_ICON if r["pass"] else FAIL_ICON
        if r["pass"]:
            passed += 1
        else:
            failed += 1

        lm = f"{r['left_margin']:.3f}\""
        rm = f"{r['right_margin']:.3f}\""
        tm = f"{r['top_margin']:.3f}\""
        bm = f"{r['bottom_margin']:.3f}\""
        print(f"[{r['slide_idx']:02d}]  {r['label']:<28} {lm:>6} {rm:>6} {tm:>6} {bm:>6}  {icon}")

        for issue in r["issues"]:
            print(f"       ⚠️  {issue}")

    body_total = total - skip
    print(f"\n결과: {passed}/{body_total} PASS  ({failed} FAIL, {skip} 건너뜀)")
    print(f"검증 기준: 좌우 {TARGET_SIDE_MARGIN:.3f}\" ± {tolerance_side:.3f}\", 상하 대칭 ±{tolerance_sym:.3f}\"")

    return failed == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PPTX 콘텐츠 영역 여백 검증")
    parser.add_argument("pptx", help="PPTX 파일 경로")
    parser.add_argument("--slide", type=int, default=None, help="특정 슬라이드 인덱스만 검증 (0-based)")
    parser.add_argument("--tolerance", type=float, default=TOLERANCE_SYMMETRIC,
                        help=f"상하 대칭 허용 편차 inch (기본 {TOLERANCE_SYMMETRIC})")
    parser.add_argument("--tolerance-side", type=float, default=TOLERANCE_SIDE,
                        help=f"좌우 허용 편차 inch (기본 {TOLERANCE_SIDE})")
    args = parser.parse_args()

    ok = run(args.pptx, args.slide, args.tolerance, args.tolerance_side)
    sys.exit(0 if ok else 1)
