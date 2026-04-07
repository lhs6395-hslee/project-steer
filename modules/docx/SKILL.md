---
name: module-docx
description: >
  Creates and manages Word documents including project reports, style-guided
  documents, and general-purpose documents. Use when user asks to "create document",
  "write report", "generate DOCX", "결과보고서", "문서 작성", "보고서 생성",
  "스타일 가이드 문서", or "범용 문서".
metadata:
  author: harness-team
  version: 1.1.0
  module: docx
  category: document-creation
  mcp-server: docx
  checklist:
    - completeness
    - formatting
    - content_accuracy
    - section_structure
    - style_compliance
---

# DOCX Module

## Instructions

### Capabilities

- 프로젝트 결과보고서 생성
- 스타일 가이드 기반 공식 문서 작성
- 범용 문서 생성 및 수정
- 헤딩 계층, 테이블, 목록 등 서식 적용
- 목차 자동 생성

### Workflow 1: 프로젝트 결과보고서

#### Step 1: 데이터 수집
- WBS에서 전체 태스크 완료 현황 추출
- 주요 마일스톤 달성 여부 확인
- 이슈/리스크 이력 수집

#### Step 2: 문서 구조
- 표지: 프로젝트명, 기간, 작성자, 버전
- 개요: 프로젝트 배경 및 목적
- 수행 내역: 단계별 수행 결과
- 산출물 목록: 생성된 문서/코드/데이터 목록
- 이슈 및 해결: 발생 이슈와 대응 내역
- 결론 및 향후 계획

#### Step 3: 스타일 적용
- 조직 스타일 가이드에 맞는 폰트, 여백, 헤딩 스타일
- 표지 디자인 템플릿 적용
- 페이지 번호, 머리글/바닥글

### Workflow 2: 범용 문서

#### Step 1: 요구사항 파악
- 문서 유형 (보고서, 제안서, 매뉴얼, 메모 등)
- 대상 독자 및 목적
- 필요 섹션 및 콘텐츠

#### Step 2: 문서 생성
- 적절한 헤딩 계층 구조
- 본문 콘텐츠 작성
- 테이블, 그림, 참조 삽입

#### Step 3: 검증
- 모든 섹션 존재 여부 확인
- 헤딩 계층 일관성 검증
- 스타일 가이드 준수 확인
