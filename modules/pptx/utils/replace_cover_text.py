"""
replace_cover_text.py
---------------------
표지 슬라이드 텍스트 교체 유틸리티 (서식 보존 방식).

규칙:
- tf.clear() 금지 — 기존 run XML의 <a:rPr>를 보존
- 텍스트박스 크기(width, height) 절대 변경 금지
- 폰트 크기 절대 변경 금지
- Shape[3], Shape[4] (회사 소개) 수정 금지

사용법:
    python modules/pptx/utils/replace_cover_text.py \\
        --template modules/pptx/templates/pptx_template.pptx \\
        --output output/pipeline_test.pptx \\
        --title "파이프라인 동작 테스트" \\
        --subtitle "단일 슬라이드 PPTX 생성 검증" \\
        --date "04/15"
"""

import argparse
import copy
import shutil
import sys
from pathlib import Path
from lxml import etree

from pptx import Presentation
from pptx.util import Pt


# ── XML 네임스페이스 ──────────────────────────────────────────────────────────
_NSMAP = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}


def _get_a_r_elements(para_xml):
    """<a:p> 안의 모든 <a:r> 요소 반환."""
    return para_xml.findall("a:r", _NSMAP)


def _get_a_t_element(r_xml):
    """<a:r> 안의 <a:t> 요소 반환."""
    return r_xml.find("a:t", _NSMAP)


def replace_text_preserve_format(tf, new_texts: list[str]):
    """
    텍스트 프레임의 텍스트를 서식 보존 방식으로 교체한다.

    Args:
        tf: python-pptx TextFrame 객체
        new_texts: 교체할 문자열 리스트. 각 항목 = 한 줄(단락).
                   빈 단락은 "" 사용.

    동작:
    - 기존 단락의 run[0]의 XML (<a:rPr>) 을 복제하여 각 새 단락의 기본 포맷으로 사용
    - tf.clear() 미사용 — XML 직접 조작
    - 텍스트박스 크기/폰트 크기 변경 없음
    """
    txBody = tf._txBody  # lxml element

    # 1) 기존 <a:p> 목록 수집
    existing_paras = txBody.findall("a:p", _NSMAP)
    if not existing_paras:
        raise RuntimeError("TextFrame에 단락이 없습니다.")

    # 2) 원본 첫 번째 단락의 첫 run <a:r> XML을 포맷 템플릿으로 저장
    first_para = existing_paras[0]
    first_runs = _get_a_r_elements(first_para)
    if not first_runs:
        raise RuntimeError("첫 단락에 run이 없습니다.")
    # 포맷 템플릿: run XML 딥카피
    run_template_xml = copy.deepcopy(first_runs[0])

    # 3) 기존 단락 중 첫 번째를 제외한 나머지 제거
    for para in existing_paras[1:]:
        txBody.remove(para)

    # 4) 기존 단락 내 run 정리 — run 하나만 남기고 나머지 제거
    first_para_runs = _get_a_r_elements(first_para)
    for r in first_para_runs[1:]:
        first_para.remove(r)

    # 5) 첫 번째 단락 첫 run 텍스트 설정
    first_single_run = _get_a_r_elements(first_para)[0]
    a_t = _get_a_t_element(first_single_run)
    if a_t is not None:
        a_t.text = new_texts[0] if new_texts else ""
    else:
        # <a:t> 없으면 추가
        a_t_el = etree.SubElement(first_single_run, f"{{{_NSMAP['a']}}}t")
        a_t_el.text = new_texts[0] if new_texts else ""

    # 6) 추가 단락(2줄 이상) 처리
    # 새 단락 삽입 위치: 기존 첫 단락 바로 뒤
    insert_after = first_para
    for line_text in new_texts[1:]:
        # 새 <a:p> 복제 (기존 단락 구조 복제)
        new_para_xml = copy.deepcopy(first_para)

        # 새 단락의 run 리스트 초기화 (run 하나만 유지)
        new_para_runs = _get_a_r_elements(new_para_xml)
        for r in new_para_runs[1:]:
            new_para_xml.remove(r)

        # 새 run 텍스트 설정
        new_run = _get_a_r_elements(new_para_xml)[0]
        new_a_t = _get_a_t_element(new_run)
        if new_a_t is not None:
            new_a_t.text = line_text
        else:
            a_t_el = etree.SubElement(new_run, f"{{{_NSMAP['a']}}}t")
            a_t_el.text = line_text

        # txBody에 삽입 (insert_after 다음 위치)
        insert_idx = list(txBody).index(insert_after) + 1
        txBody.insert(insert_idx, new_para_xml)
        insert_after = new_para_xml

    print(f"  → 교체 완료: {new_texts}")


def main():
    parser = argparse.ArgumentParser(description="표지 텍스트 교체 (서식 보존)")
    parser.add_argument("--template", required=True, help="입력 템플릿 PPTX 경로")
    parser.add_argument("--output", required=True, help="출력 PPTX 경로")
    parser.add_argument("--title", required=True, help="제목 텍스트")
    parser.add_argument("--subtitle", required=True, help="부제 텍스트")
    parser.add_argument("--date", required=True, help="날짜 MM/DD")
    args = parser.parse_args()

    template_path = Path(args.template)
    output_path = Path(args.output)

    if not template_path.exists():
        print(f"ERROR: 템플릿 파일 없음: {template_path}", file=sys.stderr)
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 템플릿을 출력 경로로 복사 후 수정
    shutil.copy2(template_path, output_path)

    prs = Presentation(str(output_path))
    slide = prs.slides[0]  # 표지 = 첫 번째 슬라이드

    # Shape 인덱스 정의 (cover slide layout 기준)
    TITLE_SHAPE_IDX = 2    # TextBox 19 — 제목 (큰 제목 영역)
    SUBTITLE_SHAPE_IDX = 5 # TextBox 25 — 부제
    DATE_SHAPE_IDX = 8     # TextBox 10 — 날짜 00/00
    # 수정 금지: shape[3] TextBox 23, shape[4] TextBox 24

    shapes = list(slide.shapes)

    print("\n[1] 제목 교체: Shape[2] TextBox 19")
    replace_text_preserve_format(
        shapes[TITLE_SHAPE_IDX].text_frame,
        [args.title]
    )

    print("\n[2] 부제 교체: Shape[5] TextBox 25")
    replace_text_preserve_format(
        shapes[SUBTITLE_SHAPE_IDX].text_frame,
        [args.subtitle]
    )

    print("\n[3] 날짜 교체: Shape[8] TextBox 10")
    replace_text_preserve_format(
        shapes[DATE_SHAPE_IDX].text_frame,
        [args.date]
    )

    # 크기 불변 검증
    for idx, label in [(TITLE_SHAPE_IDX, "Title"), (SUBTITLE_SHAPE_IDX, "Subtitle"), (DATE_SHAPE_IDX, "Date")]:
        s = shapes[idx]
        print(f"  [검증] Shape[{idx}] ({label}): w={s.width}, h={s.height} — 크기 불변")

    prs.save(str(output_path))
    print(f"\n✅ 저장 완료: {output_path}")

    # 보존 검증
    prs2 = Presentation(str(output_path))
    slide2 = prs2.slides[0]
    shapes2 = list(slide2.shapes)
    print("\n[검증] 저장 후 텍스트 확인:")
    for idx, label in [(TITLE_SHAPE_IDX, "제목"), (SUBTITLE_SHAPE_IDX, "부제"), (DATE_SHAPE_IDX, "날짜")]:
        text = shapes2[idx].text_frame.text
        print(f"  Shape[{idx}] ({label}): '{text}'")

    # shape[3], [4] 수정 안됐는지 확인
    orig_prs = Presentation(str(template_path))
    orig_shapes = list(orig_prs.slides[0].shapes)
    for idx in [3, 4]:
        orig_text = orig_shapes[idx].text_frame.text
        curr_text = shapes2[idx].text_frame.text
        match = "✅ PRESERVED" if orig_text == curr_text else "❌ MODIFIED"
        print(f"  Shape[{idx}] (회사 소개): {match} — '{curr_text[:40]}...'")

if __name__ == "__main__":
    main()
