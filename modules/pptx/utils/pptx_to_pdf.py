#!/usr/bin/env python3
"""
PPTX → PDF → PNG 변환 유틸리티

PPTX를 슬라이드별 PNG로 변환한다. 내부적으로:
  1. python-pptx로 각 슬라이드를 SVG-like 구조로 파싱
  2. reportlab으로 PDF 생성
  3. poppler(pdftoppm)로 PNG 추출

사용법:
    python pptx_to_pdf.py <file.pptx> --output-dir /tmp/slides [--slides 8,9,10]

요구사항:
    pip install python-pptx reportlab
    brew install poppler  (pdftoppm)

macOS / Linux / Windows 모두 동작.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def _register_korean_font() -> str:
    """시스템에서 한글 폰트를 찾아 reportlab에 등록. 등록된 폰트명 반환."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    candidates = [
        ("/System/Library/Fonts/Supplemental/AppleGothic.ttf", "AppleGothic"),
        ("/System/Library/Fonts/AppleGothic.ttf", "AppleGothic"),
        ("/Library/Fonts/NanumGothic.ttf", "NanumGothic"),
        ("~/Library/Fonts/NanumGothic.ttf", "NanumGothic"),
    ]
    for path, name in candidates:
        full = os.path.expanduser(path)
        if os.path.exists(full):
            pdfmetrics.registerFont(TTFont(name, full))
            return name
    return "Helvetica"  # 폴백


def pptx_to_pdf_via_script(pptx_path: str, pdf_path: str) -> None:
    """
    python-pptx + reportlab으로 PPTX → PDF 변환.
    텍스트/도형 위치를 실좌표 기반으로 PDF에 배치.
    """
    from pptx import Presentation
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import white, black

    korean_font = _register_korean_font()

    prs = Presentation(pptx_path)

    # 슬라이드 크기 (EMU → inch)
    slide_w = prs.slide_width / 914400
    slide_h = prs.slide_height / 914400

    page_size = (slide_w * inch, slide_h * inch)
    c = canvas.Canvas(pdf_path, pagesize=page_size)

    for slide_idx, slide in enumerate(prs.slides):
        # 배경색 (테마에서 가져오기 어려우므로 흰색 기본)
        c.setFillColor(white)
        c.rect(0, 0, slide_w * inch, slide_h * inch, fill=1, stroke=0)

        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue

            # 좌표 변환 (pptx: 좌상단 원점, reportlab: 좌하단 원점)
            x = shape.left / 914400 * inch
            y_top = shape.top / 914400
            w = shape.width / 914400 * inch
            h = shape.height / 914400 * inch
            # reportlab y: 슬라이드 높이 - top - height
            y = (slide_h - y_top - shape.height / 914400) * inch

            c.setFillColor(black)
            for para in shape.text_frame.paragraphs:
                text = para.text
                if not text.strip():
                    continue
                # 폰트 크기
                try:
                    font_size = para.runs[0].font.size / 12700 if para.runs and para.runs[0].font.size else 12
                except:
                    font_size = 12
                c.setFont(korean_font, min(font_size, 36))
                c.drawString(x, y + h - font_size * 1.2, text[:80])
                y -= font_size * 1.4

        c.showPage()

    c.save()


def pdf_to_png(pdf_path: str, output_dir: str, slides: list[int] | None = None, dpi: int = 150) -> list[str]:
    """pdftoppm으로 PDF → PNG 변환."""
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    prefix = str(output_dir_path / "slide")

    if slides:
        # 특정 슬라이드만
        results = []
        for s in slides:
            cmd = ["pdftoppm", "-png", f"-r", str(dpi), "-f", str(s), "-l", str(s), pdf_path, prefix]
            subprocess.run(cmd, check=True, capture_output=True)
            results.extend(sorted(output_dir_path.glob(f"slide-{s:03d}*.png")))
        return [str(p) for p in results]
    else:
        cmd = ["pdftoppm", "-png", "-r", str(dpi), pdf_path, prefix]
        subprocess.run(cmd, check=True, capture_output=True)
        return sorted(str(p) for p in output_dir_path.glob("slide-*.png"))


def convert_pptx_to_slides(
    pptx_path: str,
    output_dir: str,
    slides: list[int] | None = None,
    dpi: int = 150,
) -> list[str]:
    """
    PPTX → PDF → PNG 전체 파이프라인.

    Args:
        pptx_path: 입력 .pptx 파일
        output_dir: PNG 저장 디렉토리
        slides: 변환할 슬라이드 번호 목록 (1-based). None이면 전체.
        dpi: PNG 해상도

    Returns:
        생성된 PNG 파일 경로 목록
    """
    pdf_path = str(Path(output_dir) / "slides.pdf")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print(f"  PPTX → PDF: {pptx_path}")
    pptx_to_pdf_via_script(pptx_path, pdf_path)
    print(f"  PDF → PNG (dpi={dpi})")
    png_files = pdf_to_png(pdf_path, output_dir, slides=slides, dpi=dpi)
    print(f"  생성된 PNG: {len(png_files)}장")
    return png_files


def main():
    parser = argparse.ArgumentParser(description="PPTX → 슬라이드별 PNG 변환")
    parser.add_argument("pptx", help=".pptx 파일 경로")
    parser.add_argument("--output-dir", "-o", default="/tmp/pptx_slides", help="PNG 출력 디렉토리")
    parser.add_argument("--slides", "-s", help="변환할 슬라이드 번호 (예: 8,9,10). 미지정 시 전체")
    parser.add_argument("--dpi", type=int, default=150, help="PNG 해상도 (기본 150)")
    args = parser.parse_args()

    slides = [int(s) for s in args.slides.split(",")] if args.slides else None

    png_files = convert_pptx_to_slides(
        pptx_path=args.pptx,
        output_dir=args.output_dir,
        slides=slides,
        dpi=args.dpi,
    )

    for f in png_files:
        print(f"  → {f}")


if __name__ == "__main__":
    main()
