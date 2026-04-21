---
name: module-google_workspace-gmail
description: >
  Gmail 이메일 발송·수신·검색·레이블 관리. "이메일 보내줘", "메일 검색",
  "주간보고 발송", "받은메일 확인", "레이블 정리" 등 Gmail 관련 작업에 사용.
metadata:
  author: harness-team
  version: 1.0.0
  module: google_workspace
  service: gmail
  mcp-server: google-workspace
  checklist:
    - recipient_verified
    - subject_and_body_complete
    - attachments_validated
    - label_applied
---

# Gmail Service

`[공식]` github.com/taylorwilsdon/google_workspace_mcp — Gmail: search, retrieve, send, manage labels/filters/drafts, batch operations

## 파이프라인 vs 직접실행 판단 기준

**파이프라인 필수:**
- 다수 수신자 일괄 발송 (3명 이상)
- 템플릿 기반 반복 발송 (주간보고 등)
- 첨부파일 + 본문 동적 생성 복합 작업

**직접실행 허용:**
- 단건 이메일 발송
- 이메일 검색·조회
- 레이블 관리
- 사용자가 "직접실행" 명시 시

---

## MCP 도구 매핑

`[공식]` workspace-mcp Gmail tools

| 작업 | MCP 도구 | 비고 |
|------|---------|------|
| 이메일 검색 | `gmail_search_emails` | Gmail 검색 문법 지원 |
| 이메일 읽기 | `gmail_get_email` | message_id 기반 |
| 이메일 발송 | `gmail_send_email` | to/cc/bcc/subject/body/attachments |
| 초안 생성 | `gmail_create_draft` | 검토 후 발송 플로우에 사용 |
| 초안 발송 | `gmail_send_draft` | draft_id 기반 |
| 초안 목록 | `gmail_list_drafts` | — |
| 레이블 목록 | `gmail_list_labels` | 시스템 + 사용자 레이블 |
| 레이블 생성 | `gmail_create_label` | name, color 지정 가능 |
| 레이블 적용 | `gmail_modify_labels` | add/remove labels on message |
| 필터 생성 | `gmail_create_filter` | 자동 분류 규칙 |
| 배치 수정 | `gmail_batch_modify` | 다수 메일 일괄 레이블·읽음 처리 |

---

## Workflow 1: 이메일 발송

### Step 1: 내용 확인
- 수신자(to), 참조(cc), 제목(subject), 본문(body) 확인
- 첨부파일 경로 및 존재 여부 확인
- HTML 또는 Plain Text 형식 결정

### Step 2: 초안 생성 (선택)
검토가 필요한 경우 `gmail_create_draft` → 사용자 확인 후 `gmail_send_draft`

검토 불필요한 경우 `gmail_send_email` 직접 실행

### Step 3: 발송 검증
- 발송 완료 message_id 확인
- 필요 시 레이블 적용 (`gmail_modify_labels`)

---

## Workflow 2: 이메일 검색·조회

### Step 1: 검색 쿼리 작성
Gmail 검색 문법 사용:

| 문법 | 예시 | 의미 |
|------|------|------|
| `from:` | `from:user@example.com` | 발신자 |
| `to:` | `to:me` | 수신자 |
| `subject:` | `subject:주간보고` | 제목 포함 |
| `after:` | `after:2026/04/01` | 날짜 이후 |
| `before:` | `before:2026/04/21` | 날짜 이전 |
| `has:attachment` | — | 첨부파일 있음 |
| `is:unread` | — | 읽지 않은 메일 |
| `label:` | `label:주간보고` | 레이블 필터 |

### Step 2: 결과 처리
- `gmail_search_emails`로 message_id 목록 획득
- `gmail_get_email`로 상세 내용 읽기

---

## Workflow 3: 레이블 관리

### Step 1: 현재 레이블 확인
`gmail_list_labels`로 기존 레이블 목록 확인

### Step 2: 레이블 생성/적용
- 신규 레이블: `gmail_create_label` (name, backgroundColor 지정)
- 메일에 적용: `gmail_modify_labels` (add_label_ids / remove_label_ids)
- 자동 분류: `gmail_create_filter` (from/to/subject 조건 + 레이블 액션)

### Step 3: 일괄 처리
대량 메일 정리 시 `gmail_batch_modify` 사용

---

## Workflow 4: 주간보고 발송 (파이프라인)

Dooray 모듈과 연동하여 주간보고 내용을 이메일로 발송하는 표준 플로우:

```
1. Dooray에서 주간보고 데이터 수집 (dooray 모듈)
2. 보고서 내용 → HTML 이메일 본문 생성
3. 첨부파일(PPTX/DOCX) Drive 업로드 → 공유 링크 생성 (drive 모듈)
4. gmail_create_draft → 사용자 검토
5. 승인 후 gmail_send_draft 발송
6. 발송된 메일에 '주간보고' 레이블 적용
```

---

## 참조

- MCP 서버: `modules/google_workspace/SKILL.md`
- Drive 연동: `modules/google_workspace/drive/SKILL.md`
- Dooray 연동: `modules/dooray/SKILL.md`
