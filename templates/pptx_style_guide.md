# PowerPoint Generation System - Complete Specification

**Version**: v5.1 (2026-02-26)
**Purpose**: 이 문서 시리즈만으로 AI가 모든 Python 파일을 100% 동일하게 재생성할 수 있는 완전한 시스템 명세

## Related Documents

| File | Contents |
|------|----------|
| `powerpoint-guide.md` | 아키텍처, 스티어링 포맷, 레이아웃 참조 (이 문서) |
| `powerpoint-code-generate.md` | `generate.py` + `generate_ppt.sh` 소스코드 |
| `powerpoint-code-cover-toc.md` | `powerpoint_cover.py` + `powerpoint_toc.py` 소스코드 |
| `powerpoint-code-content.md` | `powerpoint_content.py` 소스코드 Part 1 (유틸리티 + 레이아웃 1~13) |
| `powerpoint-code-content-2.md` | `powerpoint_content.py` 소스코드 Part 2 (다이어그램 헬퍼 + 레이아웃 14~27 + 라우터) |

---

## System Architecture

```
[Steering File]     →  [generate.py]      →  [Rendering Modules]  →  [.pptx]
rayhli-eks_guide_2026.py      orchestration         powerpoint_cover.py
ss_db_migration_      (template copy,        powerpoint_toc.py
resume.py              section removal,       powerpoint_content.py
(data only)            slide management)      (38 layout renderers)
```

## Dependencies

```bash
pip install python-pptx lxml pillow
```

- `python-pptx`: PowerPoint 생성/수정
- `lxml`: XML 파싱 (섹션 제거용)
- `pillow` (PIL): 이미지 종횡비 계산 (선택사항)
- `duckduckgo_search`: 이미지 검색 (선택사항, 현재 비활성)

## File Structure

```
ppt-mcp/
├── generate_ppt.sh              # Shell wrapper (one-line 실행)
├── generate.py                  # Orchestration script
├── rayhli-eks_guide_2026.py            # Steering file - AWS EKS Guide (data only)
├── rayhli-ss_db_migration_resume.py    # Steering file - DB Migration Resume (data only)
├── powerpoint_content.py        # 38 layout renderers (35 unique + 3 aliases) + utility functions
├── powerpoint_cover.py          # Cover slide renderer
├── powerpoint_toc.py            # TOC slide renderer
├── icons/                       # 40 PNG icons (512x512)
├── architecture/                # Diagram PNG files
├── screenshots/                 # UI screenshot PNG files
├── template/
│   └── 2025_PPT_Template_FINAL.pptx  # PPT template (13.33" × 7.50")
└── results/                     # Generated PPT output
```

## Template Requirements

PPT 템플릿은 다음 슬라이드 구조를 가져야 함:
- **Index 0**: Cover slide (표지)
- **Index 1**: TOC slide (목차)
- **Index 7**: Body slide (본문 - 이 레이아웃을 복제하여 본문 슬라이드 생성)
- **Last slide**: Ending slide (감사합니다 - 보존됨)
- **Slide dimensions**: 13.333" × 7.500"

## Icons (40 Total)

```
analysis, aurora, auto_mode, aws_account, billing, chat, cicd, cli,
cluster_delete, config, console, container, cutover, dashboard, database,
deploy, dms, eks, eksctl, encryption, gitops, helm, k8s_version, kubectl,
kubernetes, load_balancer, microservices, migration, monitoring, network,
performance, pipeline, schema, security, server, service, storage,
terraform, timeline, verification
```

- Format: PNG, 512×512 pixels, transparent background
- Naming: lowercase, underscores for spaces (e.g., `load_balancer.png`)
- Location: `icons/` folder
- Fallback: 아이콘 파일 없으면 파란색 원형 표시

---

## Constants & Design System

### Fonts (FONTS dict)

| Key | Value | Usage |
|-----|-------|-------|
| `HEAD_TITLE` | "프리젠테이션 7 Bold" | 슬라이드 제목 (28pt) |
| `HEAD_DESC` | "프리젠테이션 5 Medium" | 슬라이드 설명 (12pt) |
| `BODY_TITLE` | "Freesentation" | 본문 제목/강조 |
| `BODY_TEXT` | "Freesentation" | 본문 텍스트 |

### Colors (COLORS dict)

| Key | RGB | Usage |
|-----|-----|-------|
| `PRIMARY` | (0, 67, 218) | 제목, 강조, 배지 |
| `BLACK` | (0, 0, 0) | 본문 텍스트 |
| `DARK_GRAY` | (33, 33, 33) | 진한 회색 텍스트 |
| `GRAY` | (80, 80, 80) | 설명글 |
| `BG_BOX` | (248, 249, 250) | 박스 배경 |
| `BG_WHITE` | (255, 255, 255) | 흰색 배경 |
| `BORDER` | (220, 220, 220) | 테두리 |
| `TERMINAL_BG` | (48, 10, 36) | 터미널 배경 (Ubuntu 보라색) |
| `TERMINAL_TITLEBAR` | (44, 44, 44) | 터미널 타이틀 바 |
| `TERMINAL_TEXT` | (102, 204, 102) | 터미널 텍스트 (초록) |
| `TERMINAL_COMMENT` | (150, 150, 150) | 터미널 주석 (회색) |
| `TERMINAL_RED` | (255, 95, 86) | macOS 빨강 버튼 |
| `TERMINAL_YELLOW` | (255, 189, 46) | macOS 노랑 버튼 |
| `TERMINAL_GREEN` | (39, 201, 63) | macOS 초록 버튼 |
| **Semantic Colors** | | |
| `SEM_RED` / `_BG` / `_TEXT` | (185,28,28) / (254,242,242) / (127,29,29) | 주의/필수 |
| `SEM_ORANGE` / `_BG` / `_TEXT` | (194,65,12) / (255,247,237) / (154,52,18) | 경고/핵심 |
| `SEM_GREEN` / `_BG` / `_TEXT` | (4,120,87) / (236,253,245) / (6,95,70) | 긍정/완료 |
| `SEM_BLUE` / `_BG` / `_TEXT` | (30,58,138) / (239,246,255) / (30,64,175) | 참조/조건 |
| `CALLOUT_BG` | (30, 58, 138) | 콜아웃 배경 (진한 파랑) |
| `CALLOUT_TEXT` | (219, 234, 254) | 콜아웃 본문 (밝은 파랑) |

### Layout Coordinates (LAYOUT dict)

| Key | Value | Description |
|-----|-------|-------------|
| `SLIDE_TITLE_Y` | 0.6" | 헤더 상단 |
| `SLIDE_DESC_Y` | 0.6" | 설명글 상단 |
| `BODY_START_Y` | 2.0" | 본문 시작점 |
| `BODY_LIMIT_Y` | 7.2" | 본문 한계선 |
| `MARGIN_X` | 0.5" | 좌우 여백 |
| `SLIDE_W` | 13.333" | 슬라이드 너비 |

---

## Steering File Format

steering file은 `presentation_data` 딕셔너리 하나만 정의하는 순수 데이터 파일입니다.

```python
# -*- coding: utf-8 -*-
"""Presentation Data File"""

presentation_data = {
    "cover": {
        "title": "프레젠테이션 제목",
        "subtitle": "부제목"
    },
    "sections": [
        {
            "section_title": "1. 섹션 제목",
            "slides": [
                {
                    "l": "layout_name",    # 레이아웃 종류
                    "t": "슬라이드 제목",   # 헤더 좌측
                    "d": "슬라이드 설명",   # 헤더 우측
                    "data": {              # 레이아웃별 데이터
                        # ...
                    }
                }
            ]
        }
    ]
}
```

### Data Nesting Pattern

모든 레이아웃은 `data.data.data` 3중 중첩 구조:
- Level 1: `slide_info` (t, d, l, data)
- Level 2: `wrapper = data.get('data', {})` → body_title, body_desc, data
- Level 3: `content = wrapper.get('data', {})` → 실제 콘텐츠

예외: `challenge_solution`, `before_after` — Level 2에서 직접 데이터 읽음

---

## Available Layouts (38종: 고유 35종 + alias 3종)

| # | Layout | Code | Data Keys | 비고 |
|---|--------|------|-----------|------|
| 1 | Bento Grid | `bento_grid` | main, sub1, sub2 | 좌 50% + 우 2분할 |
| 2 | Three Cards | `3_cards` | card_1, card_2, card_3 | 아이콘+제목+본문 |
| 3 | Grid 2×2 | `grid_2x2` | item1, item2, item3, item4 | compact 모드 |
| 4 | Quad Matrix | `quad_matrix` | (grid_2x2와 동일) | `grid_2x2` alias |
| 5 | Process Arrow | `process_arrow` | steps[]{title,body,search_q} | 쉐브론+본문 박스 |
| 6 | Phased Columns | `phased_columns` | steps[]{title,body,search_q} | 단계별 컬럼+그라데이션 |
| 7 | Timeline | `timeline_steps` | steps[]{date,desc} | 숫자 배지+카드 |
| 8 | Challenge/Solution | `challenge_solution` | challenge, solution | 좌우+화살표 (wrapper 레벨) |
| 9 | Comparison VS | `comparison_vs` | item_a_title/body, item_b_title/body | VS 원형 |
| 10 | Comparison Table | `comparison_table` | columns[], rows[] | 3열 표 |
| 11 | Detail Image | `detail_image` | title, body, search_q | 상단 텍스트+하단 이미지 |
| 12 | Image Left | `image_left` | image_path, bullets[] | 좌 이미지+우 불릿 |
| 13 | Architecture Wide | `architecture_wide` | col1, col2, col3 | 상단 다이어그램+하단 3열 |
| 14 | Key Metric | `key_metric` | (3_cards와 동일) | `3_cards` alias |
| 15 | Detail Sections | `detail_sections` | overview, highlight, condition, diagram | 좌 멀티섹션+우 다이어그램 |
| 16 | Table Callout | `table_callout` | columns[], rows[], callout | 테이블+추천박스 |
| 17 | Full Image | `full_image` | image_path/search_q, caption | 풀와이드 이미지 |
| 18 | Before/After | `before_after` | before_title/body, after_title/body | 전/후 비교 (wrapper 레벨) |
| 19 | Icon Grid | `icon_grid` | items[]{icon,title,desc} | 3열×N행 아이콘 그리드 |
| 20 | Numbered List | `numbered_list` | items[]{title,desc} | 번호형 세로 리스트 |
| 21 | Stats Dashboard | `stats_dashboard` | metrics[]{value,unit,label,desc} | KPI 대형 숫자 |
| 22 | Quote Highlight | `quote_highlight` | quote, author, role | 인용문 강조 |
| 23 | Pros & Cons | `pros_cons` | subject, pros[], cons[] | 장단점 비교 |
| 24 | Do / Don't | `do_dont` | do_items[], dont_items[] | Best Practice |
| 25 | Split Text+Code | `split_text_code` | description, bullets[], code_title, code | 설명+코드 병렬 |
| 26 | Pyramid Hierarchy | `pyramid_hierarchy` | levels[]{label,desc,color} | 피라미드 계층 |
| 27 | Cycle Loop | `cycle_loop` | steps[]{label,desc}, center_label | 순환 프로세스 |
| 28 | Venn Diagram | `venn_diagram` | circles[]{label,desc,color}, center_label | 좌측 3원 벤 + 우측 설명 카드 |
| 29 | SWOT Matrix | `swot_matrix` | quadrants[]{label,title,items[],color} | 2×2 SWOT 분석 |
| 30 | Center Radial | `center_radial` | center{label,desc}, directions[]{label,desc,color} | 중심 ROUNDED_RECT + 4방향 카드 |
| 31 | Funnel | `funnel` | stages[]{label,value,desc,color} | 퍼널 다이어그램 |
| 32 | Zigzag Timeline | `zigzag_timeline` | steps[]{date,title,desc,color} | 지그재그 타임라인 |
| 33 | Fishbone Cause-Effect | `fishbone_cause_effect` | effect, categories[]{label,causes[],color} | 피쉬본 원인-결과 |
| 34 | Org Chart | `org_chart` | root{label,desc}, children[]{label,desc,items[],color} | 조직도/트리 |
| 35 | Temple Pillars | `temple_pillars` | roof{label}, pillars[]{label,desc,color}, foundation{label} | 기둥형 구조도 |
| 36 | Infinity Loop | `infinity_loop` | left_loop[],right_loop[],left_label,right_label,center_label | 무한 순환 루프 |
| 37 | Speedometer Gauge | `speedometer_gauge` | value,segments[]{label,color},title | 스피도미터 게이지 |
| 38 | Mind Map | `mind_map` | center{label}, branches[]{label,sub_branches[],desc,color} | 좌측 방사형 맵 + 우측 설명 카드 |

### Detail Sections Diagram Types

`detail_sections` 레이아웃의 우측 다이어그램은 4가지 type 지원:

| Type | Description | Data Key |
|------|-------------|----------|
| `flow` | 수직 박스+화살표 흐름도 (기본값) | items[] |
| `layers` | 수평 계층 다이어그램 | layers[] |
| `compare` | 좌우 비교 다이어그램 | sides[] |
| `process` | 좌→우 가로 프로세스 | steps[] |

### Phased Columns Gradient Palette

7-step gradient (dark navy → light blue):
```python
[(0,27,94), (0,45,143), (0,67,218), (59,122,237), (123,167,247), (160,195,250), (190,215,252)]
```
N개 컬럼에 대해 균등 샘플링하여 색상 배정.

### Semantic Box Styles (\_SEM\_BOX\_STYLES)

다이어그램/detail_sections에서 사용하는 의미 기반 박스 스타일:

| Key | Fill | Line | Text |
|-----|------|------|------|
| `gray` | (248,249,250) | (150,150,150) | (33,33,33) |
| `red` | (254,242,242) | (185,28,28) | (127,29,29) |
| `orange` | (255,247,237) | (194,65,12) | (154,52,18) |
| `green` | (236,253,245) | (4,120,87) | (6,95,70) |
| `blue` | (239,246,255) | (30,58,138) | (30,64,175) |
| `primary` | (239,246,255) | (0,67,218) | (30,64,175) |

---

## Generation Flow

1. `generate.py`가 steering file의 `presentation_data`를 `exec()`로 로드
2. 템플릿 복사 → 섹션 제거 (`remove_all_sections`)
3. Cover slide 업데이트 (`powerpoint_cover.update_cover_slide`)
4. TOC slide 업데이트 (`powerpoint_toc.update_toc_slide`)
   - section_title에서 `^\d+\.\s*` prefix 제거 후 전달
5. 각 section의 각 slide에 대해:
   - Body layout 복제하여 새 슬라이드 생성
   - `set_slide_title_area()`로 헤더 설정
   - `render_slide_content()`로 본문 렌더링 (layout→renderer 라우팅)
6. 불필요한 템플릿 슬라이드 삭제 (keeper_ids 기반)
7. Ending slide를 마지막으로 이동
8. 저장 → `results/{steering_basename}.pptx`

### Post-Generation: 슬라이드 타이틀 단어 잘림 검증 (필수)

PPT 생성 후 **반드시** 모든 슬라이드 타이틀의 폭을 검증해야 합니다.

**배경**: `set_slide_title_area()`는 타이틀을 4.5인치(324pt) 영역에 28pt로 렌더링합니다.
한글이 포함된 긴 타이틀은 PowerPoint가 자동 줄바꿈 시 단어 중간에서 잘릴 수 있습니다.

**검증 방법**:
```python
# PPT 생성 후 실행
from pptx import Presentation
prs = Presentation('results/output.pptx')
for i, slide in enumerate(prs.slides):
    for shape in slide.shapes:
        if shape.has_text_frame:
            text = shape.text_frame.text.strip()
            # 번호가 붙은 타이틀만 검사 (예: "1-1.", "2-3.")
            if any(text.startswith(f'{s}-') for s in ['1','2','3','4','5']):
                width_pt = 0
                for ch in text:
                    if ord(ch) > 0x2E80: width_pt += 28    # 한글/CJK
                    elif ch == ' ':      width_pt += 7      # 공백
                    elif ch in '.:/-':   width_pt += 10     # 구두점
                    else:                width_pt += 14     # 영문/숫자
                overflow = 'OVERFLOW' if width_pt > 340 else 'OK'
                print(f'Slide {i+1}: [{width_pt}pt/340pt] {overflow} | {text}')
```

**처리 규칙**:
- 실질 임계값: **~340pt** (4.5인치 영역, 실제 렌더링 기준)
- 340pt 초과 시 steering 파일의 `"t"` 값에 `\n` 삽입
- 자연스러운 단어 경계에서만 개행 (단어 중간 금지)
- **최소한만 내릴 것**: 초과분에 해당하는 마지막 단어만 2줄로 이동. 예: 16pt 초과면 마지막 1단어만 내림
- `set_slide_title_area()`는 `\n`을 인식하여 다중 문단으로 렌더링
- **사전에 미리 자르지 말 것** — 생성 후 검증하여 초과분만 개행

## Layout Diversity Rule

- 최대 3장까지 같은 레이아웃 허용
- 단, 동일 주제/로직/다른 데이터(예: 주차별 일정)는 같은 레이아웃 허용
- 예: 1주차/2주차/3주차 작업 → 모두 `process_arrow` 사용 OK

---

## Utility Functions Summary

| Function | Description |
|----------|-------------|
| `draw_body_header_and_get_y()` | 본문 헤더(제목+설명) 그리고 시작 Y 반환 |
| `calculate_dynamic_rect()` | 남은 공간 (x, y, w, h) 계산 |
| `create_content_box()` | 만능 박스 (normal/compact/terminal 모드) |
| `create_terminal_box()` | macOS 스타일 터미널 박스 |
| `draw_icon_search()` | 로컬 아이콘 로드 (없으면 파란 원형) |
| `clean_body_placeholders()` | 본문 영역(2.0"~7.2") 기존 도형 제거 |
| `_place_image_centered()` | 이미지 비율 유지 중앙 배치 |
| `_diagram_box()` | 다이어그램용 의미색상 박스 |
| `_diagram_arrow_label()` | 화살표 라벨 (⬇/➡/⬅/⬆) |
| `_diagram_shape_arrow()` | 실제 화살표 shape |
