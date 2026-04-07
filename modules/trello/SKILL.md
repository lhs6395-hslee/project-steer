---
name: module-trello
description: >
  Manages Trello kanban boards, lists, and cards for project workflow tracking.
  Use when user asks to "manage board", "move card", "update Trello",
  "칸반 보드", "카드 이동", "Trello 관리", or "보드 설정".
metadata:
  author: harness-team
  version: 1.1.0
  module: trello
  category: project-management
  mcp-server: trello
  checklist:
    - completeness
    - board_structure
    - card_detail
    - label_consistency
    - workflow_logic
---

# Trello Module

## Instructions

### Capabilities

- 칸반 보드 생성 및 구조 설정
- 리스트(워크플로우 단계) 관리
- 카드 생성, 수정, 이동
- 라벨, 담당자, 마감일 관리
- 카드 상태 일괄 업데이트

### Workflow 1: 보드 설정

#### Step 1: 보드 구조 정의
- 워크플로우 단계별 리스트 설계 (Backlog → In Progress → Review → Done)
- 라벨 체계 정의 (우선순위, 카테고리, 모듈 등)
- 팀 멤버 초대 및 역할 설정

#### Step 2: 카드 생성
- WBS 태스크를 카드로 변환
- 설명, 체크리스트, 마감일 설정
- 담당자 배정 및 라벨 부착

### Workflow 2: 카드 이동 및 상태 관리

#### Step 1: 상태 확인
- 현재 카드 위치(리스트) 확인
- 완료 조건 충족 여부 판단

#### Step 2: 카드 이동
- 완료된 카드를 다음 단계 리스트로 이동
- 이동 사유 코멘트 추가
- 관련 카드 의존성 업데이트

#### Step 3: 검증
- 모든 카드가 올바른 리스트에 위치하는지 확인
- 라벨 일관성 검증
- 마감일 초과 카드 플래그
