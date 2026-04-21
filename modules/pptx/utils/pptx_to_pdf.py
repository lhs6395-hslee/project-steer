#!/usr/bin/env python3
"""
PPTX → PDF → PNG 슬라이드 이미지 변환 유틸리티

OS별 동작:
  - macOS  : AppleScript로 PowerPoint에 PDF export 요청 → pdftoppm(poppler)으로 PNG 변환
  - Windows: pptx2pdf 패키지 (pip install docx2pdf) → pdftoppm 또는 pdf2image로 PNG 변환
  - Linux  : 미지원 — None 반환 (시각 검증 스킵)

사용법:
    python pptx_to_pdf.py <file.pptx> --output-dir /tmp/slides [--slides 8,9,10] [--dpi 150]

요구사항:
  macOS  : Microsoft PowerPoint 설치, brew install poppler
  Windows: pip install docx2pdf, poppler for Windows 또는 pip install pdf2image
"""

import argparse
import os
import platform
import subprocess
import sys
import time
from pathlib import Path


# ── OS 감지 ──────────────────────────────────────────────────────────────────

def get_os() -> str:
    s = platform.system()
    if s == "Darwin":
        return "mac"
    elif s == "Windows":
        return "windows"
    return "linux"


# ── macOS: AppleScript로 PowerPoint PDF export ────────────────────────────────

def _mac_export_pdf(pptx_path: str, pdf_path: str) -> None:
    """PowerPoint for Mac — AppleScript 'save as PDF' (화면 점유 없음, 백그라운드 동작)."""
    abs_pptx = str(Path(pptx_path).resolve())
    abs_pdf = str(Path(pdf_path).resolve())

    # 출력 디렉토리 생성 (AppleScript는 존재하지 않는 경로에 저장 불가)
    Path(abs_pdf).parent.mkdir(parents=True, exist_ok=True)

    script = f'''
tell application "Microsoft PowerPoint"
    -- 열린 프레젠테이션 중 path 매칭 찾기
    set prsCount to count of presentations
    set matchIdx to 0
    repeat with i from 1 to prsCount
        if path of presentation i is "{abs_pptx}" then
            set matchIdx to i
            exit repeat
        end if
    end repeat

    -- 없으면 열기
    if matchIdx is 0 then
        open POSIX file "{abs_pptx}"
        delay 2
        set matchIdx to count of presentations
    end if

    -- GUI 없이 백그라운드에서 PDF 저장 (EPPSaveAsFileType 0x00cc000e = save as PDF)
    save presentation matchIdx in POSIX file "{abs_pdf}" as save as PDF
end tell
'''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True
    )
    time.sleep(1)

    if not Path(abs_pdf).exists():
        raise RuntimeError(
            f"AppleScript PDF export 실패.\n"
            f"stderr: {result.stderr}\n"
            f"stdout: {result.stdout}"
        )


# ── Windows: docx2pdf (PowerPoint COM 사용) ───────────────────────────────────

def _windows_export_pdf(pptx_path: str, pdf_path: str) -> None:
    """docx2pdf로 PPTX → PDF (Windows PowerPoint COM 방식)."""
    try:
        # docx2pdf는 내부적으로 PowerPoint COM을 사용해 pptx도 처리 가능
        # (assert .docx 체크를 우회하기 위해 직접 convert_win 호출)
        from docx2pdf import convert_win
        convert_win(pptx_path, pdf_path)
    except ImportError:
        raise RuntimeError("pip install docx2pdf 필요")
    except Exception as e:
        raise RuntimeError(f"docx2pdf 변환 실패: {e}")


# ── PDF → PNG (poppler pdftoppm) ──────────────────────────────────────────────

def _pdf_to_png(pdf_path: str, output_dir: str, slides: list[int] | None, dpi: int) -> list[str]:
    """pdftoppm으로 PDF → PNG. slides는 1-based 번호 목록."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    prefix = str(out / "slide")

    if slides:
        results = []
        for s in slides:
            cmd = ["pdftoppm", "-png", "-r", str(dpi), "-f", str(s), "-l", str(s), pdf_path, prefix]
            subprocess.run(cmd, check=True, capture_output=True)
        # 생성된 파일 수집
        results = sorted(out.glob("slide-*.png"))
    else:
        cmd = ["pdftoppm", "-png", "-r", str(dpi), pdf_path, prefix]
        subprocess.run(cmd, check=True, capture_output=True)
        results = sorted(out.glob("slide-*.png"))

    return [str(p) for p in results]


# ── 공개 API ──────────────────────────────────────────────────────────────────

def convert_pptx_to_slides(
    pptx_path: str,
    output_dir: str,
    slides: list[int] | None = None,
    dpi: int = 150,
) -> list[str] | None:
    """
    PPTX → PDF → PNG 전체 파이프라인.

    Args:
        pptx_path : 입력 .pptx 파일 경로
        output_dir: PNG 저장 디렉토리
        slides    : 변환할 슬라이드 번호 목록 (1-based). None이면 전체.
        dpi       : PNG 해상도 (기본 150)

    Returns:
        생성된 PNG 파일 경로 목록, Linux이면 None (시각 검증 스킵)
    """
    os_type = get_os()

    if os_type == "linux":
        print("  [skip] Linux 환경 — 시각 검증 미지원")
        return None

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # macOS Sandbox 제약: PowerPoint는 pptx와 동일 디렉토리에만 쓰기 가능
    # → PDF를 pptx 옆에 임시 저장 후 PNG 추출, 즉시 삭제
    pptx_dir = Path(pptx_path).resolve().parent
    pdf_path = str(pptx_dir / "_slides_tmp.pdf")

    print(f"  PPTX → PDF [{os_type}]: {pptx_path}")
    if os_type == "mac":
        _mac_export_pdf(pptx_path, pdf_path)
    elif os_type == "windows":
        _windows_export_pdf(pptx_path, pdf_path)

    print(f"  PDF → PNG (dpi={dpi})")
    png_files = _pdf_to_png(pdf_path, output_dir, slides=slides, dpi=dpi)
    print(f"  생성된 PNG: {len(png_files)}장")

    # 임시 PDF 즉시 삭제
    Path(pdf_path).unlink(missing_ok=True)

    return png_files


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PPTX → 슬라이드별 PNG 변환")
    parser.add_argument("pptx", help=".pptx 파일 경로")
    parser.add_argument("--output-dir", "-o", default="/tmp/pptx_slides", help="PNG 출력 디렉토리")
    parser.add_argument("--slides", "-s", help="변환할 슬라이드 번호 (예: 8,9,10). 미지정 시 전체")
    parser.add_argument("--dpi", type=int, default=150, help="PNG 해상도 (기본 150)")
    args = parser.parse_args()

    slides = [int(s) for s in args.slides.split(",")] if args.slides else None
    result = convert_pptx_to_slides(
        pptx_path=args.pptx,
        output_dir=args.output_dir,
        slides=slides,
        dpi=args.dpi,
    )
    if result is None:
        print("시각 검증 스킵 (Linux)")
        sys.exit(0)
    for f in result:
        print(f"  → {f}")


if __name__ == "__main__":
    main()
