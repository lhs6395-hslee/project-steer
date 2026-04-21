---
paths:
  - "modules/pptx/**"
  - "results/pptx/**"
---

# PPTX 직접실행 주의사항

pptx 파일 작업 시 아래 규칙을 위반하면 즉시 사용자에게 보고한다.
파이프라인 원칙(MCP 우선, 병렬 실행 등)은 `CLAUDE.md` 참조.
생성 옵션·검증 절차·유틸 매핑은 `modules/pptx/SKILL.md` 참조.

---

1. **git restore/checkout 전 반드시 확인** — `git diff HEAD -- <file>` 또는 `git status`로 미커밋 변경사항 존재 여부 확인 후 실행. 미커밋 파일이 있으면 git checkout 대신 백업 후 수동 복원.

2. **zipfile 직접실행 삽입 규칙:**
   - 본문 슬라이드는 **반드시 템플릿 10페이지(idx 9)**에서 복사. 이전 슬라이드(결과물)에서 복사 금지
   - 다중 슬라이드 삽입 시 기존 파일 패치 금지 → **원본을 base로 재조립** (MISTAKES #30)
   - 원본의 max_rId/max_sldId 구한 후 순차 증가. rId 충돌 금지
   - 삽입 후 검증 4종 순서대로 실행:
     1. `pptx_integrity_check.py --fix`
     2. `verify_margins.py`
     3. `check_textbox_overflow.py --fix`
     4. `fix_panel_positions.py`

3. **OOXML 직접 생성 시 스펙 준수** (MISTAKES #29):
   - `p:txBody` 자식: `[a:bodyPr, a:lstStyle, a:p...]`만 허용
   - `a:rPr` 자식 순서: `[ln, solidFill, ..., latin, ea, cs, ...]` (fill → font)
   - 템플릿 복사 후 `p14:creationId`를 슬라이드마다 고유값으로 교체

4. **좌표는 layout-spec.md의 EMU값 그대로 사용:**
   - 스펙 표기 `457200 (0.500")` → 코드에서 `457200` 직접 사용
   - `int(0.500 * 914400)` 변환 금지 (부동소수점 오차 원인)
   - 좌/우 여백 기준: 0.500" ± 0.060", 상/하 대칭 ± 0.060"

5. **동적 배치 규칙 — 콘텐츠 생성 후 적용:**
   - L12 변화율 배지 있음 → 내용 TextBox cy: `content_max_bottom = badge_top - 91440`
   - Swim Lane/로드맵 내부 task → row 대비 상/하 0.10" 여백 (`inner_cy = row_cy - 182880`)
   - roundRect 패널 내 왼쪽 정렬 TextBox → **x/cx만** 비율 조정 (y 변경 금지)
     `safe_x = panel_left + 0.0764 × panel_cx` / `safe_right = panel_right - 0.0764 × panel_cx`
