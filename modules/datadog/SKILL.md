---
name: module-datadog
description: >
  Manages Datadog monitors, dashboards, and alert configurations including
  creation, modification, and capture. Use when user asks to "set up monitoring",
  "create dashboard", "modify dashboard", "configure alerts", "대시보드 생성",
  "대시보드 수정", "대시보드 캡처", "모니터 관리", or "알림 설정".
metadata:
  author: harness-team
  version: 1.1.0
  module: datadog
  category: monitoring
  mcp-server: datadog
  checklist:
    - completeness
    - metric_accuracy
    - alert_threshold
    - dashboard_clarity
    - query_correctness
---

# Datadog Module

## Instructions

### Capabilities

- 모니터 생성 및 관리 (임계값 설정, 알림 라우팅)
- 대시보드 생성 및 수정
- 대시보드 캡처 (스크린샷/데이터 추출)
- 메트릭 쿼리 작성 및 검증
- 알림 에스컬레이션 설정

### Workflow 1: 모니터 관리

#### Step 1: 메트릭 식별
- 모니터링 대상 메트릭 결정
- 베이스라인 값 및 임계값 정의
- 알림 심각도 레벨 설정

#### Step 2: 모니터 생성/수정
- 임계값 조건으로 모니터 생성
- 알림 수신자 및 채널 설정
- 복구 조건 정의

#### Step 3: 검증
- 모니터 트리거 조건 테스트
- 알림 라우팅 확인
- 오탐(false positive) 가능성 평가

### Workflow 2: 대시보드 생성/수정

#### Step 1: 대시보드 설계
- 표시할 메트릭 및 위젯 유형 결정
- 레이아웃 구성 (그리드 배치)
- 필터/변수 설정

#### Step 2: 위젯 구성
- 각 위젯에 메트릭 쿼리 설정
- 시각화 유형 선택 (timeseries, toplist, heatmap 등)
- 임계값 표시선 추가

#### Step 3: 검증
- 모든 위젯이 데이터를 정상 표시하는지 확인
- 쿼리 정확성 검증
- 대시보드 가독성 평가

### Workflow 3: 대시보드 캡처

#### Step 1: 캡처 대상 확인
- 캡처할 대시보드 및 시간 범위 지정
- 필터 조건 설정

#### Step 2: 캡처 실행
- 대시보드 스크린샷 또는 데이터 추출
- 주간 보고용 이미지/데이터 생성

#### Step 3: 산출물 연동
- 캡처 결과를 Google Drive에 업로드
- PPTX 모듈에 차트 이미지 전달
