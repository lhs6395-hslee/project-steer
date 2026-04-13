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

## Instructions

### Capabilities

- MCP 도구(mcp_pptx_*)로 JSON 데이터를 직접 전달하여 프레젠테이션 생성
- 템플릿 기반 일관된 디자인 (13.333" × 7.500", 8개 레이아웃)
- 표지, 목차, 본문, 끝맺음 페이지 자동 구성
- 레이아웃 스펙: `modules/pptx/references/layout-spec.md`
- 스타일 가이드: `templates/pptx_style_guide.md` (색상, 폰트, 좌표 상수)

### 생성 방식

PPTX 생성은 두 가지 방식을 조합한다:
- **MCP 도구(mcp_pptx_*)**: 새 슬라이드 추가, 새 shape/table/chart 추가, 프레젠테이션 정보 조회, 저장
- **python-pptx 유틸리티**: 기존 shape 텍스트 교체 (MCP manage_text에 replace 미지원), 템플릿 슬라이드 삭제/이동

규칙:
- 새 콘텐츠 추가 → MCP 도구 사용
- 기존 shape 텍스트 교체 (표지/목차/끝맺음) → python-pptx 유틸리티 허용
- 유틸리티 스크립트는 `scripts/utils/`에 배치
- 템플릿(`templates/pptx_template.pptx`)에서 시작하여 슬라이드를 추가/수정한다.

### 참조 파일

- 템플릿: `templates/pptx_template.pptx`
- 레이아웃 스펙: `modules/pptx/references/layout-spec.md` (shape 좌표 EMU)
- 스타일 가이드: `templates/pptx_style_guide.md` (색상, 폰트, 레이아웃 상수)

### 필수 규칙

- 새 콘텐츠 추가: MCP 도구(mcp_pptx_*)로 수행
- 기존 shape 텍스트 교체: python-pptx 유틸리티 허용 (표지/목차/끝맺음 등 템플릿 shape 수정)
- 유틸리티 스크립트는 `scripts/utils/`에 배치
- 타이틀 잘림 검증: 타이틀 영역 4.5인치/28pt 기준 ~340pt 초과 시 자연스러운 단어 경계에서 \n 삽입 (단어 중간 금지, 생성 후 검증)

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
