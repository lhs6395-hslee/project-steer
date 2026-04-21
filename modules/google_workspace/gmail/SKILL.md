---
name: module-google_workspace-gmail
description: >
  Gmail 이메일 발송·수신·검색·레이블 관리·메일 분석. "이메일 보내줘", "메일 검색",
  "주간보고 발송", "받은메일 확인", "레이블 정리/재정의", "메일 분류 분석" 등 Gmail 관련 작업에 사용.
metadata:
  author: harness-team
  version: 2.0.0
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
- 라벨 재정의 (현재 구조 조사 → 신규 체계 설계 → 일괄 적용)
- 다수 수신자 일괄 발송 (3명 이상)
- 템플릿 기반 반복 발송 (주간보고 등)
- 메일 분석 대상 10건 이상 (검색 → 추출 → 요약 보고서)
- 첨부파일 + 본문 동적 생성 복합 작업

**직접실행 허용:**
- 단건 이메일 발송
- 이메일 검색·조회 (10건 미만)
- 단건 레이블 생성/적용
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

## Workflow 3: 레이블 재정의 (파이프라인)

망가진 레이블 구조를 조사하고 신규 체계로 전환하는 표준 플로우.

`[참조]` specs/ai-agent-engineering-spec-2026.md — Sprint_Contract recon step 패턴

### Sprint_Contract 구조

```json
{
  "task": "Gmail 레이블 재정의",
  "module": "google_workspace",
  "mode": "modify",
  "recon_step_id": 1,
  "steps": [
    {
      "id": 1,
      "action": "recon: gmail_list_labels로 현재 레이블 전체 덤프 및 문제 파악",
      "dependencies": [],
      "acceptance_criteria": ["레이블 목록 JSON 출력", "중복·손상·미사용 레이블 식별"]
    },
    {
      "id": 2,
      "action": "신규 레이블 체계 설계 및 사용자 승인",
      "dependencies": [1],
      "acceptance_criteria": ["계층 구조 확정", "사용자 승인 완료"]
    },
    {
      "id": 3,
      "action": "gmail_create_label로 신규 레이블 생성 + gmail_create_filter로 자동 분류 규칙 등록",
      "dependencies": [2],
      "acceptance_criteria": ["모든 신규 레이블 생성 확인", "필터 규칙 등록 확인"]
    },
    {
      "id": 4,
      "action": "gmail_batch_modify로 기존 메일 신규 레이블로 재분류",
      "dependencies": [3],
      "acceptance_criteria": ["재분류 대상 메일 수 확인", "기존 손상 레이블 제거 완료"]
    }
  ]
}
```

### 실행 흐름

```
Step 1 (recon)  : gmail_list_labels → 현재 구조 분석 보고
Step 2 (design) : 신규 레이블 계층 설계 → 사용자 승인 대기
Step 3 (create) : gmail_create_label (병렬 가능) + gmail_create_filter
Step 4 (migrate): gmail_batch_modify로 기존 메일 재분류
```

### 레이블 설계 원칙

- 계층 구분자: `/` (예: `업무/AWS`, `업무/프로젝트/MSK`)
- 색상 코드: backgroundColor + textColor 쌍으로 지정
- 자동 분류 필터는 레이블 생성 직후 등록
- 시스템 레이블(INBOX, SENT 등)은 수정 금지

---

## Workflow 4: 메일 분석 (파이프라인)

검색 조건으로 메일을 수집하고 분류·요약·패턴 탐지 보고서를 생성하는 플로우.

`[참조]` specs/ai-agent-engineering-spec-2026.md — Generator-Evaluator 패턴

### Sprint_Contract 구조

```json
{
  "task": "Gmail 메일 분석",
  "module": "google_workspace",
  "mode": "create",
  "steps": [
    {
      "id": 1,
      "action": "gmail_search_emails로 대상 메일 목록 수집",
      "dependencies": [],
      "acceptance_criteria": ["검색 결과 message_id 목록 확보", "건수 확인"]
    },
    {
      "id": 2,
      "action": "gmail_get_email로 각 메일 상세 내용 추출",
      "dependencies": [1],
      "acceptance_criteria": ["발신자/제목/본문/날짜 추출 완료"]
    },
    {
      "id": 3,
      "action": "분류·요약·패턴 탐지 보고서 생성",
      "dependencies": [2],
      "acceptance_criteria": ["카테고리별 분류표", "주요 키워드/발신자 통계", "요약 보고서 파일 생성"]
    }
  ]
}
```

### 분석 유형

| 분석 유형 | 설명 | 출력 |
|----------|------|------|
| 분류 분석 | 발신자·도메인·주제별 그룹핑 | 카테고리 분류표 |
| 요약 분석 | 메일 본문 핵심 내용 요약 | 요약 보고서 (Markdown) |
| 패턴 탐지 | 반복 발신자, 스팸 패턴, 미처리 메일 탐지 | 이슈 목록 |
| 액션 아이템 추출 | 메일 본문에서 할 일·마감일 추출 | 액션 아이템 목록 |

---

## Workflow 5: 이메일 작성 (직접실행)

### Step 1: 작성 컨텍스트 파악
- 목적 (회신/신규/전달) 확인
- 수신자 역할·관계 파악 (공식/비공식 문체 결정)
- 참조할 이전 메일 있으면 `gmail_get_email`로 원문 조회

### Step 2: 초안 작성
- 제목 → 인사 → 본문 → 맺음말 구조
- HTML body 권장 (서식 있는 경우)
- `gmail_create_draft`로 저장 후 사용자 검토

### Step 3: 발송
- 사용자 승인 후 `gmail_send_draft`
- 발송 후 필요 시 레이블 적용

---

## Workflow 6: 주간보고 발송 (파이프라인)

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
- 하네스 파이프라인 스펙: `specs/ai-agent-engineering-spec-2026.md`
- Drive 연동: `modules/google_workspace/drive/SKILL.md`
- Dooray 연동: `modules/dooray/SKILL.md`
