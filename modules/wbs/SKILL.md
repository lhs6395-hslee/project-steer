---
name: module-wbs
description: >
  Manages Excel-based Work Breakdown Structures with task hierarchy,
  progress tracking, and effort estimation. Use when user asks to "create WBS",
  "update progress", "track tasks", "작업 분해", "진척 관리",
  "WBS 업데이트", "Excel 작업 관리", or "일정 추적".
metadata:
  author: harness-team
  version: 1.1.0
  module: wbs
  category: project-management
  checklist:
    - completeness
    - task_hierarchy
    - dependency_validity
    - estimation_reasonableness
    - scope_coverage
---

# WBS Module

## Instructions

### Capabilities

- Excel 기반 WBS 생성 및 관리
- 태스크 계층 구조 (Phase → Work Package → Task)
- 진척률 추적 및 업데이트
- 의존성 관리 (FS, FF, SS, SF)
- 공수 추정 및 일정 산출

### Workflow 1: WBS 생성

#### Step 1: 프로젝트 범위 파악
- 프로젝트 목표 및 산출물 정의
- 주요 단계(Phase) 식별
- 범위 경계 설정

#### Step 2: 작업 분해
- 단계별 작업 패키지 분해
- 100% 규칙 적용 (하위 항목이 상위 범위를 완전히 커버)
- 일관된 분해 깊이 유지

#### Step 3: 의존성 및 추정
- 태스크 간 의존성 매핑
- 리프 레벨 태스크 공수 추정
- 순환 의존성 없음 검증

### Workflow 2: 진척 추적

#### Step 1: 현황 수집
- 각 태스크의 완료율 업데이트
- 실제 투입 공수 기록
- 지연 사유 기록

#### Step 2: 진척률 계산
- 가중 평균 기반 상위 항목 진척률 자동 계산
- 계획 대비 실적 비교
- 크리티컬 패스 지연 여부 확인

#### Step 3: 보고 데이터 생성
- 주간 보고용 진척 요약 데이터 추출
- PPTX 모듈에 전달할 차트 데이터 생성
- 지연 태스크 알림 목록 생성
