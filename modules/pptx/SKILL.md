---
name: module-pptx
description: >
  Creates and manages PowerPoint presentations including weekly plan/completion
  reports and general-purpose presentations. Use when user asks to "create presentation",
  "make slides", "generate PPTX", "weekly report deck", "주간 계획", "주간 완료",
  "프레젠테이션 생성", "슬라이드 수정", or "발표자료".
metadata:
  author: harness-team
  version: 1.1.0
  module: pptx
  category: document-creation
  mcp-server: pptx
  checklist:
    - completeness
    - slide_structure
    - content_accuracy
    - visual_consistency
    - template_compliance
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

PPTX는 MCP 도구(mcp_pptx_*)로 JSON 데이터를 직접 전달하여 생성한다.
Python 스크립트를 작성하여 생성하지 않는다.
템플릿(`templates/pptx_template.pptx`)에서 시작하여 슬라이드를 추가/수정한다.

### 참조 파일

- 템플릿: `templates/pptx_template.pptx`
- 레이아웃 스펙: `modules/pptx/references/layout-spec.md` (shape 좌표 EMU)
- 스타일 가이드: `templates/pptx_style_guide.md` (색상, 폰트, 레이아웃 상수)

### 필수 규칙

- MCP 도구로 JSON 데이터를 직접 전달하여 생성한다 (Python 스크립트 작성 금지)
- 타이틀 잘림 검증: 타이틀 영역 4.5인치/28pt 기준 ~340pt 초과 시 자연스러운 단어 경계에서 \n 삽입 (단어 중간 금지, 생성 후 검증)

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
