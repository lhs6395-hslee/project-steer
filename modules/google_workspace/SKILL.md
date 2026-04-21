---
name: module-google_workspace
description: >
  Google Workspace 서비스 통합 모듈. Gmail, Drive, Calendar, Docs, Sheets 등
  12개 서비스를 단일 MCP 서버(workspace-mcp)로 제어한다.
metadata:
  author: harness-team
  version: 2.0.0
  module: google_workspace
  mcp-server: google-workspace
---

# Google Workspace Module

MCP 서버: `uvx workspace-mcp` — 12개 서비스 100+ 도구

`[공식]` github.com/taylorwilsdon/google_workspace_mcp

## 서비스 목록

| 서비스 | SKILL.md | 상태 | 주요 용도 |
|--------|---------|------|---------|
| Gmail | `gmail/SKILL.md` | ✅ 설계 완료 | 이메일 발송·수신·검색·레이블 관리 |
| Drive | `drive/SKILL.md` | ✅ 설계 완료 | 파일 업/다운로드·폴더 관리·공유 |
| Calendar | — | 예정 | 일정 생성·조회·가용성 확인 |
| Docs | — | 예정 | 문서 생성·수정·내보내기 |
| Sheets | — | 예정 | 스프레드시트 읽기/쓰기·포맷 |
| Slides | — | 예정 | 프레젠테이션 생성·수정 |
| Chat | — | 예정 | 메시지 발송·스페이스 관리 |
| Tasks | — | 예정 | 할일 생성·관리 |
| Contacts | — | 예정 | 연락처 검색·관리 |
| Forms | — | 예정 | 폼 생성·응답 수집 |

## 공통 규칙

- 인증: OAuth 2.0/2.1 자동 처리 (workspace-mcp 내장)
- 서비스 캐시: 30분 (단일/멀티 유저 모두 지원)
- 작업 전 반드시 해당 서비스 `SKILL.md` 읽기
- 파이프라인 판단 기준: `CLAUDE.md` + 각 서비스 SKILL.md 참조
