---
name: module-dooray
description: >
  Manages Dooray tasks, weekly reports, meeting notes, and project collaboration.
  Use when user asks to "write weekly report", "create meeting notes",
  "주간보고 작성", "주간보고 발송", "회의록 작성", "미팅 기록",
  "Dooray 태스크", or "회의 정리".
metadata:
  author: harness-team
  version: 1.1.0
  module: dooray
  category: project-management
  mcp-server: dooray
  checklist:
    - completeness
    - task_assignment
    - priority_accuracy
    - milestone_alignment
    - notification_setup
---

# Dooray Module

## Instructions

### Capabilities

- 주간보고 자동 작성 및 발송
- 회의록/미팅 기록 작성
- 태스크 생성 및 관리
- 마일스톤 연동
- 알림 설정

### Workflow 1: 주간보고 자동 작성/발송

#### Step 1: 데이터 수집
- WBS에서 금주 완료/차주 계획 태스크 추출
- Trello 보드에서 카드 이동 이력 확인
- 이슈/리스크 현황 수집

#### Step 2: 보고서 작성
- 금주 수행 내역 요약
- 차주 계획 정리
- 이슈/리스크 및 대응 방안
- 요청 사항 (있을 경우)

#### Step 3: 발송
- Dooray 프로젝트에 주간보고 게시
- 관련자 멘션 및 알림 설정
- 첨부 파일 연결 (PPTX, 기타 산출물)

### Workflow 2: 회의/미팅 기록

#### Step 1: 회의 정보 수집
- 회의 제목, 일시, 참석자
- 안건 목록
- 논의 내용 (음성/텍스트 입력)

#### Step 2: 회의록 작성
- 안건별 논의 내용 정리
- 결정 사항 명시
- 액션 아이템 추출 (담당자, 마감일)

#### Step 3: 후속 처리
- 액션 아이템을 Dooray 태스크로 생성
- Trello 카드와 연동 (필요 시)
- 참석자에게 회의록 공유 및 알림
