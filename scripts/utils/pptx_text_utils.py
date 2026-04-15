#!/usr/bin/env python3
"""
PPTX Text Utility Functions
─────────────────────────────
서식 보존 텍스트 교체 유틸리티.
템플릿 shape의 scheme color(흰색), 폰트명, 크기, bold 설정을 유지하면서
텍스트만 교체한다.

CONSTRAINTS:
- tf.clear() 금지 — 기존 run XML을 복제하여 텍스트만 교체
- scheme color 보존 필수 (BACKGROUND_1 = 흰색)
"""

import copy
from lxml import etree


NS_A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
NS_P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'


def replace_text_preserve_format(shape, new_text):
    """단일 단락 텍스트를 서식 보존하면서 교체.

    첫 번째 run의 텍스트를 교체하고 나머지 run을 비운다.
    scheme color, 폰트명, 크기, bold 설정이 그대로 유지된다.

    Args:
        shape: python-pptx Shape 객체
        new_text: 교체할 텍스트
    """
    tf = shape.text_frame
    if not tf.paragraphs:
        return
    p = tf.paragraphs[0]
    if p.runs:
        # 첫 번째 run에 텍스트 설정 (서식 보존)
        p.runs[0].text = new_text
        # 나머지 run 텍스트 비우기
        for run in p.runs[1:]:
            run.text = ""
    # 나머지 단락 제거
    for para in tf.paragraphs[1:]:
        para._p.getparent().remove(para._p)


def replace_multiline_preserve_format(shape, lines, font_size_override=None):
    """멀티라인 텍스트를 서식 보존하면서 교체.

    첫 번째 단락의 서식(run XML)을 복제하여 각 줄에 적용한다.
    scheme color가 보존된다. 선택적으로 폰트 크기를 오버라이드할 수 있다.

    Args:
        shape: python-pptx Shape 객체
        lines: 교체할 텍스트 줄 목록 (list of str)
        font_size_override: 폰트 크기 오버라이드 (pt, 선택사항)
    """
    tf = shape.text_frame
    if not tf.paragraphs or not tf.paragraphs[0].runs:
        return

    # 참조 단락 XML 가져오기 (첫 번째 단락)
    ref_p = tf.paragraphs[0]._p

    # txBody에서 모든 기존 단락 제거
    txBody = tf._txBody
    for p_elem in list(txBody.iterchildren(f'{NS_A}p')):
        txBody.remove(p_elem)

    # 참조 단락을 복제하여 새 단락 생성
    for i, line in enumerate(lines):
        new_p = copy.deepcopy(ref_p)
        # 첫 번째 run에 텍스트 설정
        runs = new_p.findall(f'.//{NS_A}r')
        if runs:
            t_elem = runs[0].find(f'{NS_A}t')
            if t_elem is not None:
                t_elem.text = line
            # 폰트 크기 오버라이드 (선택사항)
            if font_size_override is not None:
                rPr = runs[0].find(f'{NS_A}rPr')
                if rPr is not None:
                    rPr.set('sz', str(int(font_size_override * 100)))  # pt → hundredths
            # 나머지 run 제거
            for extra_run in runs[1:]:
                new_p.remove(extra_run)
        txBody.append(new_p)


def estimate_text_width_pt(text, font_size_pt):
    """텍스트의 대략적인 렌더링 폭을 pt 단위로 추정.

    한글/CJK는 font_size와 동일, 영문/숫자는 font_size * 0.55, 공백은 font_size * 0.3.

    Args:
        text: 텍스트 문자열
        font_size_pt: 폰트 크기 (pt)

    Returns:
        추정 폭 (pt)
    """
    width = 0
    for ch in text:
        if ord(ch) > 0x2E80:       # CJK/한글
            width += font_size_pt
        elif ch == ' ':
            width += font_size_pt * 0.3
        elif ch in '.:/-()·—':
            width += font_size_pt * 0.4
        else:                       # 영문/숫자
            width += font_size_pt * 0.55
    return width


def auto_fit_textbox_width(shape, lines, font_size_pt, slide_w=12192000,
                            margin=457200, center=False, margin_left=None):
    """텍스트 줄 중 가장 긴 줄에 맞춰 텍스트박스 너비를 자동 조정.

    Args:
        shape: 텍스트박스 Shape 객체
        lines: 텍스트 줄 목록
        font_size_pt: 폰트 크기 (pt)
        slide_w: 슬라이드 너비 (EMU, 기본 13.333")
        margin: 좌우 최소 여백 (EMU, 기본 0.5")
        center: True면 슬라이드 중앙 배치
        margin_left: 고정 left 위치 (None이면 현재 유지)
    """
    # 1pt = 12700 EMU
    PT_TO_EMU = 12700
    max_width_pt = max(
        estimate_text_width_pt(line, font_size_pt)
        for line in lines if line
    )
    # 10% 패딩 추가
    needed_width = int(max_width_pt * PT_TO_EMU * 1.1)

    if center:
        max_allowed = slide_w - 2 * margin
        needed_width = min(needed_width, max_allowed)
        shape.width = needed_width
        shape.left = (slide_w - needed_width) // 2
    else:
        current_left = margin_left if margin_left is not None else shape.left
        max_allowed = slide_w - current_left - margin
        needed_width = min(needed_width, max_allowed)
        shape.width = needed_width
        if margin_left is not None:
            shape.left = margin_left
