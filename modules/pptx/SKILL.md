---
name: module-pptx
description: >
  Creates and manages PowerPoint presentations including weekly plan/completion
  reports and general-purpose presentations. Use when user asks to "create presentation",
  "make slides", "generate PPTX", "weekly report deck", "주간 계획", "주간 완료",
  "프레젠테이션 생성", "슬라이드 수정", or "발표자료".
metadata:
  author: harness-team
  version: 1.3.0
  module: pptx
  category: document-creation
  mcp-server: pptx
  checklist:
    - completeness
    - slide_structure
    - content_accuracy
    - visual_consistency
    - template_compliance
    - text_overflow
    - format_preservation
    - design_quality
---

# PPTX Module

## 파이프라인 vs 직접실행 판단 기준

**파이프라인 필수:**
- 다중 슬라이드 생성 (3개 이상)
- 복잡한 레이아웃 조합 (L09~L36)
- 데이터 검증이 필요한 작업

**직접실행 허용:**
- 슬라이드 1~2개 추가 (스펙 명확한 L01~L15)
- 텍스트/색상/폰트 수정 (좌표 변경 없음)
- 슬라이드 순서 변경, 삭제, 병합, 백업
- **사용자가 "직접실행" 명시 시 — 슬라이드 수·레이아웃 범위 무관**
- **캡처/이미지 보며 실시간 위치·크기 조정 시 — 반복 튜닝 특성상 직접실행 허용**

**직접실행 제약:**
- `modules/pptx/utils/` 유틸리티 또는 zipfile 방식만 사용
- 원본 파일 in-place 수정 (임시 파일 생성 금지)
- 완료 후 수동 검증 필수

---

## Instructions

### Capabilities

- MCP 도구(mcp_pptx_*)로 JSON 데이터를 직접 전달하여 프레젠테이션 생성
- 템플릿 기반 일관된 디자인 (13.333" × 7.500", 8개 레이아웃)
- 표지, 목차, 본문, 끝맺음 페이지 자동 구성
- 레이아웃 스펙: `modules/pptx/references/layout-spec.md`
- 스타일 가이드: `modules/pptx/templates/pptx_style_guide.md` (색상, 폰트, 좌표 상수)

### 생성 방식

PPTX 생성은 두 가지 방식을 조합한다:
- **MCP 도구(mcp_pptx_*)**: 새 슬라이드 추가, 새 shape/table/chart 추가, 프레젠테이션 정보 조회, 저장
- **python-pptx 유틸리티**: 기존 shape 텍스트 교체 (MCP manage_text에 replace 미지원), 템플릿 슬라이드 삭제/이동

규칙:
- 새 콘텐츠 추가 → MCP 도구 사용 (위반 시 Reviewer가 constraint_violation critical 처리)
- 기존 shape 텍스트 교체 (표지/목차/끝맺음) → python-pptx 유틸리티 허용
- 유틸리티 스크립트는 `modules/pptx/utils/`에 배치
- 템플릿(`modules/pptx/templates/pptx_template.pptx`)에서 시작하여 슬라이드를 추가/수정한다.

#### 프레젠테이션 생성 옵션

신규 프레젠테이션을 만들 때 아래 3가지 옵션 중 하나를 선택한다.
**실행 전 항상 슬라이드 구성 Plan 표를 제시하고 사용자 승인 후 진행.**

| 옵션 | 방식 | 소스 파일 | 파이프라인 | 선택 기준 |
|------|------|---------|----------|---------|
| **Option 1** | MCP 도구로 슬라이드/콘텐츠 직접 생성 | `pptx_template.pptx` | 필수 | 슬라이드 3개↑ 또는 복잡한 레이아웃 |
| **Option 2** | 템플릿 base 슬라이드 복사 후 내용 채움 | `pptx_template.pptx` | 직접실행 허용 | 새 주제, 새 프레젠테이션 표준 방식 |
| **Option 3** | 완성된 레이아웃 슬라이드 XML 복사 후 텍스트 교체 | `pptx_layout_intro.pptx` | 직접실행 허용 | 기존 검증 레이아웃을 그대로 재사용 |

---

**Option 1 — MCP 도구 직접 생성**

1. `pptx_template.pptx`를 열고 불필요한 슬라이드 삭제
2. `mcp__pptx__add_slide`로 슬라이드 추가
3. 각 슬라이드에 `add_shape` / `manage_text` / `manage_image` / `add_table` 등 MCP 도구로 콘텐츠 배치
4. 표지/목차/끝맺음 텍스트는 `populate_placeholder` 또는 python-pptx `replace_text_preserve_format`으로 교체
5. `mcp__pptx__save_presentation`으로 저장
6. python-pptx로 새 shape 직접 생성 금지 — 기존 shape 텍스트 교체만 허용
7. 파이프라인 필수: Planner → Executor(병렬) → Reviewer(병렬)

---

**Option 2 — 템플릿 기반 zipfile 조립**

1. `pptx_template.pptx`에서 표지/목차/끝맺음 슬라이드를 그대로 복사
2. 본문 슬라이드: `pptx_template.pptx` **slide10.xml(idx 9)** 복사 × 필요한 장 수
3. 각 본문 슬라이드에 python-pptx로 콘텐츠(텍스트/도형) 채움
4. `presentation.xml` sldIdLst 재구성 (새 슬라이드 ID 순서대로)
5. **sectionLst 재구성 필수**: 표지 / 목차 / 본문 / 끝맺음 4개 섹션을 새 슬라이드 ID로 매핑
6. TOC 재구성 + 중제목 라벨 업데이트:
   ```bash
   python modules/pptx/utils/fix_toc.py results/pptx/<파일>.pptx \
     --sections "섹션1" "섹션2" ... \
     --labels 3:"L09. AS-IS":"설명" 4:"L12. KPI":"설명" ...
   ```
   - 섹션이 6개 이상이면 두 번째 목차 슬라이드 자동 생성 (5개씩 페이징)
   - `--labels` : 본문 슬라이드 번호별 중제목 라벨(TextBox 17) + 설명(TextBox 18) 교체
7. 아래 검증 3종 **순서대로** 실행, 모두 PASS 확인:
   ```bash
   python modules/pptx/utils/pptx_integrity_check.py results/pptx/<파일>.pptx --fix
   python modules/pptx/utils/verify_margins.py results/pptx/<파일>.pptx
   python modules/pptx/utils/check_textbox_overflow.py results/pptx/<파일>.pptx --fix
   ```

---

**Option 3 — 레이아웃 재사용 zipfile 조립**

1. 콘텐츠 계획 수립 → 각 슬라이드에 맞는 레이아웃 선택 (layout-spec.md 참조)
2. `pptx_layout_intro.pptx`에서 선택한 레이아웃 슬라이드 XML을 복사
3. 표지/목차/끝맺음도 `pptx_layout_intro.pptx`의 해당 슬라이드에서 복사
4. python-pptx로 텍스트만 교체 — 레이아웃 구조/도형/좌표 변경 금지
5. 소스는 `pptx_layout_intro.pptx`만 사용 (`pptx_template.pptx` 혼용 금지)
6. **sectionLst 재구성 필수**: Option 2와 동일 (4개 섹션 → 새 슬라이드 ID 매핑)
7. TOC 재구성 + 중제목 라벨 업데이트 (Option 2와 동일):
   ```bash
   python modules/pptx/utils/fix_toc.py results/pptx/<파일>.pptx \
     --sections "섹션1" "섹션2" ...  --labels 3:"L09. AS-IS":"설명" ...
   ```
8. 아래 검증 3종 **순서대로** 실행, 모두 PASS 확인:
   ```bash
   python modules/pptx/utils/pptx_integrity_check.py results/pptx/<파일>.pptx --fix
   python modules/pptx/utils/verify_margins.py results/pptx/<파일>.pptx
   python modules/pptx/utils/check_textbox_overflow.py results/pptx/<파일>.pptx --fix
   ```

### MCP 도구 → python-pptx 유틸 매핑

| 작업 | MCP (필수) | python-pptx 유틸 (허용 범위) |
|------|-----------|---------------------------|
| 새 슬라이드 추가 | `mcp__pptx__add_slide` | 금지 |
| 도형 추가 | `mcp__pptx__add_shape` | 금지 |
| 텍스트박스 추가 | `mcp__pptx__manage_text(operation="add")` | 금지 |
| 이미지/아이콘 추가 | `mcp__pptx__manage_image(operation="add")` | 금지 |
| 표 추가 | `mcp__pptx__add_table` | 금지 |
| 저장 | `mcp__pptx__save_presentation` | `prs.save()` 절대 금지 |
| 기존 텍스트 교체 | — | `modules/pptx/utils/pptx_text_utils.py` |
| 슬라이드 삭제/정렬 | — | `modules/pptx/utils/delete_extra_slides.py`, `reorder_slides.py` |
| 좌표 검증/안전 저장 | — | `modules/pptx/utils/pptx_safe_edit.py` |
| 텍스트 오버플로우 검증/수정 | — | `modules/pptx/utils/check_textbox_overflow.py` |
| TOC 재구성 + 중제목 라벨 업데이트 | — | `modules/pptx/utils/fix_toc.py` |
| ZIP/XML 수정 | — | `modules/pptx/utils/pptx_zip_cleaner.py` |
| 프레젠테이션 병합 | — | `modules/pptx/utils/merge_presentations.py` |

> 레이아웃 생성 중 새로운 유틸리티가 추가되면 이 표와 `.claude/agents/executor.md`를 함께 업데이트한다.

### 참조 파일

- 템플릿: `modules/pptx/templates/pptx_template.pptx` (Option 2 소스)
- 레이아웃: `modules/pptx/templates/pptx_layout_intro.pptx` (Option 3 소스 — 완성된 레이아웃 슬라이드)
- 레이아웃 스펙: `modules/pptx/references/layout-spec.md` (shape 좌표 EMU)
- 스타일 가이드: `modules/pptx/templates/pptx_style_guide.md` (색상, 폰트, 레이아웃 상수)

### 필수 규칙

- 새 콘텐츠 추가: MCP 도구(mcp_pptx_*)로 수행
- 기존 shape 텍스트 교체: python-pptx 유틸리티 허용 (표지/목차/끝맺음 등 템플릿 shape 수정)
- 유틸리티 스크립트는 `modules/pptx/utils/`에 배치
- 타이틀 잘림 검증: 타이틀 영역 4.5인치/28pt 기준 ~340pt 초과 시 자연스러운 단어 경계에서 \n 삽입 (단어 중간 금지, 생성 후 검증)
- **중제목(subtitle) 디자인 규칙**:
  - **텍스트 박스 크기(width, height) 절대 변경 금지** — 원래 레이아웃 스펙 그대로 유지
  - **폰트 크기 절대 변경 금지** — 텍스트박스/폰트 크기 조정은 절대 하지 않음
  - 최대 2줄까지 허용 (3줄 이상 금지)
  - 단어 중간에서 줄바꿈 금지 (예: `Ar/row` ✗, `Col/umns` ✗, `아키텍/처` ✗)
  - **단어가 잘리는 경우 → 잘리는 단어 바로 앞에서 개행** (예: `Process Ar/row` → `Process\nArrow`, `Phased Col/umns` → `Phased\nColumns`)
  - 개행 이동으로 3줄이 되면 → 텍스트를 요약하여 2줄로 맞춤 (텍스트 크기/박스 변경 ✗)

### 아이콘 사용 규칙 (CRITICAL)

- **파란색 원형(Oval + 텍스트 심볼) fallback 금지** — 프레젠테이션 품질을 떨어뜨리므로 절대 사용하지 않는다
- **우선순위**:
  1. `modules/pptx/icons/png/` 폴더에서 매핑 가능한 PNG 검색 (glob으로 확인)
  2. 없으면 외부에서 적절한 아이콘 다운로드 (WebFetch 등)
  3. 다운로드도 불가능하면 → 작업 중단하고 사용자에게 보고 (placeholder 사용 금지)
- 아이콘 크기: 411,480 × 411,480 EMU (0.45" × 0.45")

### 레이아웃별 흐름도/도식도 존재 규칙

| 레이아웃 | 흐름도/도식도/이미지 | 비고 |
|---------|-------------------|------|
| L02 Three Cards (3페이지) | **필수** | 상단 다이어그램 존 없으면 FAIL |
| L04 Process Arrow | **선택** | 있으면 카드 아이콘 제거, 없으면 각 카드 우하단 아이콘 필수 |
| L05 Phased Columns | **선택** | 있으면 카드 아이콘 제거, 없으면 각 카드 우하단 아이콘 필수 |
| 기타 레이아웃 | 선택 | — |

- L04/L05에 흐름도 배너를 추가할 경우: 콘텐츠를 아래로 shift하고 7.0" 이내로 카드 높이 조정
- 흐름도 존 규격: left=457200, top≈2.55", w=11277600, h≈0.90" EMU, fill=#F8F9FA, border=PRIMARY
- **카드 우하단 아이콘 규격** (흐름도/도식도 없을 때): 각 카드마다 오른쪽 하단에 1개씩 배치
  - 크기: 411,480 × 411,480 EMU (0.45" × 0.45")
  - 위치: `left = 카드_right - 0.65"`, `top = 카드_bottom - 0.65"`
  - 모서리 여백: 아이콘 우하단 끝과 카드 모서리 사이 최소 0.20" 확보 (너무 붙으면 FAIL)
  - 아이콘은 카드 내용/주제에 맞는 PNG 선택 (modules/pptx/icons/png/ 폴더 우선)
  - 카드 4개면 아이콘 4개, 카드 5개면 아이콘 5개 — 카드 수와 1:1 대응
  - 흐름도 추가 시 전체 아이콘 제거, 흐름도 제거 시 전체 아이콘 복원 (항상 둘 중 하나 존재)
  - **슬라이드 전체 우하단 단일 아이콘 배치 금지** — 반드시 각 카드별로 배치

### 레이아웃 구조 규칙 (주제 독립적)

레이아웃 구조와 품질 기준은 **주제와 무관하게** 항상 동일하게 적용된다.
내용이 MSK든 다른 주제든 아래 구조 규칙을 따른다.

| 레이아웃 | 왼쪽/상단 영역 | 오른쪽/하단 영역 | 필수 요소 |
|---------|-------------|----------------|---------|
| L01 Bento | 왼쪽 50%: 해당 주제 **개요/특징** (오른쪽과 다른 내용) | 우측 2분할: 세부 항목 2개 | 하단 흐름도/도식도 (선택) |
| L02 Three Cards | 상단: 흐름도/도식도 (**필수**) | 하단: 3개 카드 (균등 분할) | 흐름도 색상 다양화 |
| L03 Grid 2x2 | 2×2 그리드 | 각 셀: 아이콘+제목+본문 | 아이콘 실제 PNG 필수 |
| L04 Process Arrow | 본문제목/설명 + 화살표 4단계 | 단계별 카드 | 우하단 아이콘 (흐름도 없을 때) |
| L05 Phased Columns | 본문제목/설명 + 4단계 컬럼 | 컬럼별 내용 | 컬럼 색상 다양화 + 우하단 아이콘 |

**왼쪽/상단 영역 내용 원칙:**
- L01 왼쪽 카드: 우측 카드들의 내용을 **요약/통합**하는 상위 개념 또는 **다른 관점**의 내용. 우측 내용 그대로 복사 금지.
- L02 상단 흐름도: 주제의 핵심 흐름(데이터/프로세스/단계)을 시각화. 색상은 역할별로 다양화(시작=ORANGE, 핵심=PRIMARY, 끝=GREEN 등)

### 도형 겹침 규칙

- **의도된 겹침 (허용)**: 카드 배경 RR 위에 자신의 자식 텍스트박스가 올라가는 z-order 구조 — 정상
- **비의도 겹침 (금지)**: 서로 다른 컨테이너/카드에 속한 텍스트박스끼리 겹침 — FAIL
- **흰 텍스트 on 투명배경 (허용)**: 채색된 RR 위에 올라간 투명 배경 텍스트박스의 WHITE 텍스트는 RR 색상이 어두우면 정상 (false positive 아님)
- **흰 텍스트 on 밝은 배경 (금지)**: fill=#F8F9FA/#FFFFFF 등 밝은 배경 위 WHITE 텍스트 — CRITICAL FAIL

### 본문 콘텐츠 배치 규칙

- **중앙 정렬 필수**: 다이어그램, 카드 그룹, 리스트 등 본문 콘텐츠 블록은 슬라이드 좌우 중앙에 배치. `start_left = (SLIDE_W - total_block_width) / 2`
- **좌우 여백 대칭**: 왼쪽 여백 ≈ 오른쪽 여백 (±0.1" 이내)
- **도형/카드 제목**: 프리젠테이션 7 Bold, **14pt**, PRIMARY 색상
- **도형/카드 내용**: Freesentation, **13pt**, DARK_GRAY 색상
- **배지/라벨 텍스트**: 프리젠테이션 7 Bold, 14pt, WHITE 색상 (PRIMARY 배경)
- **본문 제목**: Freesentation, **16pt**, PRIMARY. 중제목 아래 1.75"에 배치
- **본문 설명글**: Freesentation, 13pt, DARK_GRAY. 본문 제목 아래
- **본문 영역**: body_start_y(2.0") ~ body_limit_y(7.0") 범위 내 배치
- **하단 여백 필수**: 모든 콘텐츠는 7.0" 이내. 슬라이드 바닥에 붙지 않도록 최소 0.3" 여백
- **도형 내부 텍스트**: 별도 textbox가 아닌 shape의 text_frame에 직접 삽입. bodyPr inset으로 상하좌우 내부 여백 균등 (0.12" 권장)
- **텍스트 수직 정렬**: 단일 텍스트 도형은 `anchor='ctr'`(Middle). 복합 텍스트는 상단 정렬 + inset 패딩
- **요소 간 최소 간격**: 0.2"
- **요소 겹침 금지**: 텍스트가 텍스트박스를 넘어서 다른 요소와 겹치지 않도록 사전 검증
- **본문 텍스트 오버플로우 금지 (CRITICAL)**: 본문 영역(카드/화살표/컬럼 내부) 텍스트가 해당 shape 높이를 넘어서는 안 됨.
  - 텍스트박스 크기/폰트 크기는 변경하지 않음
  - 텍스트가 넘칠 경우 → 내용을 요약하여 해당 shape 높이 내에 들어오도록 맞춤
  - 요약 기준: 핵심 키워드 중심으로 압축, 의미 손실 최소화
  - 생성 후 반드시 검증: `(텍스트 줄 수 × 줄 높이) ≤ shape.height`

### 표지 규칙

- **서식 보존**: 표지 shape 텍스트 교체 시 `tf.clear()` 금지. 기존 run XML을 복제하여 텍스트만 교체 (`replace_text_preserve_format` / `replace_multiline_preserve_format` 사용). scheme color(흰색)가 보존되어야 함.
- **제목 텍스트박스**: 좌우 중앙 배치 (left=1.67", width=10.0"), 높이 2.8" (50pt 3줄 수용), 수직 중앙 (top=1.63")
- **부제 텍스트박스**: 제목과 동일 좌우 배치, top = 제목 bottom + 0.15" 간격
- **날짜 형식**: "MM/DD" (오늘 날짜 기준, 템플릿 원본 "00/00" 패턴)
- **회사 소개 shape[3],[4]**: 수정하지 않음 (원본 유지)

### 섹션(Section) 관리

- 템플릿의 기존 8개 섹션(표지/대목차/중목차/가이드라인/본문/차트/이미지영상강조/아이콘)은 산출물 구조에 맞게 재구성
- 산출물 섹션: 표지 / 목차 / 본문 / 끝맺음 (슬라이드 ID 기반 매핑)
- 빌드 스크립트에서 sectionLst XML을 직접 조작하여 교체

### 끝맺음 규칙

- **템플릿 그대로 사용**: 끝맺음 슬라이드(index 40)는 수정하지 않음. "Thank You" + 원본 태그라인 유지.
- 태그라인을 변경해야 하는 특수한 경우에만 `replace_text_preserve_format` 사용 (서식 보존 필수)
- 끝맺음은 항상 산출물의 마지막 슬라이드에 위치

### Workflow 1: 주간 계획/완료 프레젠테이션

#### Step 1: 데이터 수집
- WBS 모듈에서 금주/차주 태스크 목록 추출
- Trello 보드에서 카드 상태 확인
- 이전 주간 보고서 참조 (있을 경우)

#### Step 2: 슬라이드 구성
- 표지: 프로젝트명, 보고 기간, 작성자
- 금주 완료 사항: 태스크별 완료 상태 요약
- 차주 계획: 예정 태스크, 담당자, 일정
- 이슈/리스크: 현재 블로커 및 대응 방안
- 진척률: 전체 진행률 차트

#### Step 3: 시각 요소 적용
- 진행률 차트 (bar/pie)
- 상태별 색상 코딩 (완료=녹색, 진행중=파랑, 지연=빨강)
- 일관된 폰트 및 레이아웃

### Workflow 2: 범용 프레젠테이션

#### Step 1: 요구사항 파악
- 프레젠테이션 목적 및 대상 청중 확인
- 필요한 슬라이드 수, 콘텐츠 주제 파악
- 템플릿/색상 스킴 선호도 확인

#### Step 2: 구조 설계
- 타이틀 슬라이드
- 목차/아젠다
- 본문 슬라이드 (텍스트, 차트, 이미지 조합)
- 요약/결론
- Q&A 또는 부록

#### Step 3: 콘텐츠 생성 및 검증
- 각 슬라이드에 콘텐츠 배치
- 시각적 일관성 확인
- 데이터 정확성 검증

### Troubleshooting

**Error: Template not found**
Solution: 기본 템플릿으로 폴백, 경고 로그 기록

**Error: Chart data mismatch**
Solution: 차트 생성 전 데이터 차원 검증

---

## Known Pitfalls / 반복 실수 주의사항

과거 세션에서 반복된 실수 패턴. 작업 전 반드시 확인한다.

### MCP 원칙 위반
- **#1 MCP 우선 원칙 위반**: `add_shape()`, `add_textbox()`, `add_picture()` 등 python-pptx로 새 콘텐츠 생성 금지. 반드시 `mcp__pptx__*` 도구 사용
- **#2 MCP 불가 도형 무단 대체**: CHEVRON 등 MCP로 추가 불가능한 도형은 임의로 ROUNDED_RECTANGLE로 대체 금지. 반드시 사용자에게 보고하고 승인 받기
- **#3 `prs.save()` 금지**: python-pptx `prs.save()` 직접 호출 시 비순차 슬라이드 번호로 인해 슬라이드 덮어쓰기 발생. 반드시 `PptxSafeEditor` (`modules/pptx/utils/pptx_safe_edit.py`) 또는 `mcp__pptx__save_presentation` 사용

### 보더/Fill 규칙
- **#4 `style.lnRef` 파란색 오적용**: shape에 명시적 `ln` 없으면 `style.lnRef.scheme=accent1`(파란색)이 기본 적용됨. MCP/Python으로 생성한 모든 shape은 `ln noFill` 또는 원하는 색으로 명시 필요
- **#5 보더 규칙 slide_idx 하드코딩 금지**: fill color 기반으로 동적 판별. vibrant fill → line noFill, light fill (#E6F0FF 등) → border DCDCDC (6350)

### 텍스트/폰트
- **#6 카드 내용 폰트 크기**: 카드/도형 내 본문 텍스트는 **13pt** 기준. 12pt로 생성하면 Reviewer 즉시 FAIL
- **#7 중제목 텍스트박스 크기 변경 금지**: `subtitle` textbox의 width/height는 절대 불변. 텍스트가 넘치면 요약하여 맞춤

### 아이콘
- **#8 파란색 원형 fallback 금지**: 실제 PNG 아이콘 없으면 placeholder 사용 금지. `modules/pptx/icons/png/`에서 검색 → 외부 다운로드 → 불가능하면 사용자 보고
- **#9 아이콘 크기 규격**: 411,480 × 411,480 EMU (0.45" × 0.45") 고정. 임의 크기 사용 금지

### 위치/겹침
- **#10 auto_position margin 오설정**: `auto_position_card_content()`의 margin_emu 기본값은 `91440`(0.25cm). `274320`(0.76cm) 사용 시 flow label 포함 전체 이동 오류 발생
- **#11 x-column 정렬 sub-label 제외**: vibrant RR와 동일 x-column의 TextBox(flow label, sub-label)는 `auto_position_card_content()`에서 이동 제외. `vibrant_xs` ±0.25cm tolerance로 제외 로직 적용
- **#12 텍스트 겹침 수정 하드코딩 금지**: corner overlap 수정은 `check_text_corner_overlap()` + `min_safe_y_for_textbox()` 동적 계산 사용. 레이아웃별 delta 하드코딩 금지

### 색상/접근성
- **#13 밝은 배경 위 흰색 텍스트 금지**: `E6F0FF` 등 밝은 배경(WCAG 대비율 < 4.5:1)에 FFFFFF 텍스트 사용 금지. `1B3A5C`(대비율 10.12:1) 등 어두운 색상 사용

### Reviewer 검증
- **#14 Reviewer python-pptx 검증 필수**: PPTX 모듈 작업이면 Reviewer는 반드시 python-pptx로 결과 파일을 직접 열어 shape 좌표/크기/텍스트 검증. text-only 리뷰 허용 안 됨
