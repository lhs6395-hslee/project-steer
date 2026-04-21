---
paths:
  - "modules/pptx/**"
  - "results/pptx/**"
---

# PPTX 에이전트 행동 주의사항

과거 세션에서 반복된 실수 패턴 — 이 항목을 위반하면 즉시 사용자에게 보고한다.

1. **세션 시작 시 CLAUDE.md/모듈 SKILL.md 반드시 읽기** — 읽지 않고 작업 시작 금지
2. **MCP 우선 원칙** — 새 콘텐츠(도형/텍스트박스/이미지) 추가는 MCP 도구만 사용. Python으로 직접 생성 금지 (예: `add_shape()`, `add_textbox()`, `add_picture()`, `prs.save()`)
3. **Executor/Reviewer는 step 정보만 수신** — 전체 Sprint_Contract 전달 금지 (context 낭비 + isolation 위반)
4. **복원 전 버전 확인** — git restore/checkout 전 반드시 커밋 해시와 타임스탬프 확인 후 사용자 승인 받기
5. **단계별 완료 보고 + 토큰 출력** — Planner/각 Executor/각 Reviewer 완료 시 "✅ [역할] STEP N input: N, output: N tokens" 형식으로 즉시 보고. 파이프라인 최종 완료 시 단계별 합산 테이블 출력
6. **병렬→순차 전환 금지** — 병렬 실행이 합의된 상태에서 사용자 동의 없이 순차로 변경 금지
7. **MCP 불가 항목 즉시 보고** — MCP로 구현 불가능한 항목 발견 시 즉시 중단하고 대안 제시 (무단 대체 금지)
8. **python-pptx 허용 범위** — `modules/pptx/utils/` 내 지정된 유틸만 사용. 새 shape 생성 용도로 쓰면 위반
9. **슬라이드 삽입 규칙 (zipfile 직접실행 시):**
   - 본문 슬라이드는 **반드시 템플릿 10페이지(idx 9)**에서 복사. 이전 슬라이드(결과물)에서 복사 금지
   - 다중 슬라이드 삽입 시 기존 파일을 패치하지 말고, **원본을 base로 깨끗하게 재조립** (MISTAKES #30)
   - 원본의 max_rId/max_sldId를 구한 후 순차 증가. rId 충돌 금지
   - 삽입 후 반드시 아래 검증 4종 **순서대로** 실행:
     1. `pptx_integrity_check.py --fix` → OOXML 구조 검증/자동수정
     2. `verify_margins.py` → 여백/좌표 검증
     3. `check_textbox_overflow.py --fix` → 텍스트 오버플로우 감지 및 자동 수정
     4. `fix_panel_positions.py` → roundRect 패널 내 **왼쪽 정렬** TextBox 비율 기반 자동 배치 (가운데/오른쪽 정렬 제외)
   - 네 검증 모두 PASS해야 작업 완료. FAIL 시 수정 후 재검증
12. **동적 배치 규칙 — 콘텐츠 생성 후 반드시 적용:**
    - L12 변화율 배지 있음 → 내용 TextBox cy 동적 제한: `content_max_bottom = badge_top - 91440`
    - Swim Lane/로드맵 내부 task → row 배경 대비 상/하 0.10" 여백 (`inner_cy = row_cy - 182880`)
    - roundRect 패널 내 왼쪽 정렬 TextBox → **x/cx만** 비율로 조정 (y 변경 금지!)
      `safe_x = panel_left + 0.0764 × panel_cx` / `safe_right = panel_right - 0.0764 × panel_cx`
      → y 변경 시 큰제목→소제목→구분선→본문 순서 무너져 겹침 발생
    - `pptx_safe_edit.py::fix_text_corner_overlap()` — x-only 자동 수정 함수
10. **새 도형 프로그래밍 생성 시 OOXML 스펙 준수** (MISTAKES #29):
    - `p:txBody` 자식: `[a:bodyPr, a:lstStyle, a:p...]`만 허용
    - `a:rPr` 자식 순서: `[ln, solidFill, ..., latin, ea, cs, ...]` (fill → font)
    - 템플릿 복사 후 `p14:creationId`를 슬라이드마다 고유값으로 교체
11. **좌표/여백은 layout-spec.md의 EMU값을 직접 사용:**
    - 스펙 형식: `457200 (0.500")` → EMU값 = 457200, 인치값 = 0.500"
    - 코드에서는 **EMU값을 그대로** 사용. `int(인치값 * 914400)` 으로 변환하지 않음 (MISTAKES #29 좌표 오류 원인)
    - 좌/우 여백 기준: 0.500" ± 0.060", 상/하 대칭 ± 0.060"
