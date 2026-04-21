---
name: module-google_workspace
description: >
  Manages Google Drive file operations including upload, download, organization,
  and document editing. Use when user asks to "upload file", "download from Drive",
  "organize files", "edit document", "산출물 업로드", "파일 다운로드",
  "Drive 정리", "문서 수정", or "폴더 관리".
metadata:
  author: harness-team
  version: 1.1.0
  module: google_workspace
  category: file-management
  mcp-server: google-workspace
  checklist:
    - completeness
    - file_organization
    - permission_correctness
    - naming_convention
    - folder_structure
---

# Google Drive Module

## Instructions

### Capabilities

- 산출물 업로드 및 다운로드
- 문서 수정 (Google Docs/Sheets 연동)
- 폴더 계층 구조 생성 및 관리
- 공유 권한 설정
- 네이밍 컨벤션 적용

### Workflow 1: 산출물 업/다운로드

#### Step 1: 대상 파일 확인
- 업로드/다운로드 대상 파일 목록 확인
- 대상 폴더 경로 확인
- 파일 형식 및 크기 검증

#### Step 2: 파일 전송
- 지정 폴더에 파일 업로드 또는 다운로드
- 네이밍 컨벤션 적용 (프로젝트명_날짜_버전)
- 중복 파일 처리 (덮어쓰기/버전 관리)

#### Step 3: 검증
- 파일 전송 완료 확인
- 파일 무결성 검증
- 공유 권한 자동 설정

### Workflow 2: 문서 수정

#### Step 1: 문서 열기
- Google Drive에서 대상 문서 식별
- 문서 유형 확인 (Docs, Sheets, Slides)
- 현재 내용 읽기

#### Step 2: 수정 실행
- 요청된 변경 사항 적용
- 서식 유지 및 일관성 확인
- 변경 이력 코멘트 추가

#### Step 3: 검증 및 공유
- 수정 내용 정확성 확인
- 관련자에게 수정 알림
- 버전 히스토리 확인

### Workflow 3: 폴더 구조 관리

#### Step 1: 구조 설계
- 프로젝트 기반 폴더 계층 설계
- 네이밍 컨벤션 정의
- 권한 모델 계획

#### Step 2: 생성 및 정리
- 폴더 계층 순서대로 생성
- 기존 파일 올바른 위치로 이동
- 네이밍 컨벤션 일괄 적용

#### Step 3: 권한 설정
- 폴더별 공유 권한 설정
- 권한 상속 확인
- 접근 모델 문서화
