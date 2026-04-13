# Project-Steer 요구사항 문서

## 프로젝트 개요

하네스 엔지니어링 기반 멀티 에이전트 파이프라인으로, 7개 업무 모듈(pptx, docx, wbs, trello, dooray, gdrive, datadog)의 산출물을 자동 생성·검증한다.

기술 스펙 레퍼런스: `specs/ai-agent-engineering-spec-2026.md` (새 기술 추가/requirements 업데이트 시에만 참조)

## 아키텍처

- Primary: Claude Code (`claude --print` 서브에이전트)
- Sync: Kiro (`.kiro/steering/`, `.kiro/hooks/`, `invokeSubAgent`), Antigravity (`.gemini/`, `.agent/`)
- 설정 흐름: Claude Code → Kiro/Antigravity (단방향)

## 에이전트 역할

| 에이전트 | 스킬 | 역할 |
|---------|------|------|
| Planner | `skills/planner/SKILL.md` | 요구사항 분석, 실행 계획 생성 |
| Executor | `skills/executor/SKILL.md` | 계획 실행, 산출물 생성 |
| Reviewer | `skills/reviewer/SKILL.md` | 적대적 독립 검증 |
| Orchestrator | `skills/orchestrator/SKILL.md` | 파이프라인 제어, 재시도 루프 |

## 모듈 요구사항

### M1: PPTX (프레젠테이션)

- MCP 도구로 JSON 데이터를 직접 전달하여 생성 (Python 스크립트 작성 금지)
- 템플릿 기반: `templates/pptx_template.pptx` (8개 레이아웃)
- 레이아웃 스펙: `modules/pptx/references/layout-spec.md`
- 스타일 가이드: `templates/pptx_style_guide.md`
- 타이틀 잘림 검증: 340pt 초과 시 `\n` 삽입
- 표지 → 목차 → 본문(N-N. 제목) → Thank You 구조

### M2: DOCX (문서)

- 스타일 가이드: `templates/docx_style_guide.md`
- 템플릿: `templates/docx_template.docx`
- 표지(28pt Bold #1A1A2E) → History → 목차 → 본문 → 푸터(PAGE 9pt)
- 테이블: 헤더 #1B3A5C navy + white, 짝수행 #F2F2F2
- 문체: 현재형 `~한다` 통일

### M3: WBS (작업 분해 구조)

- Excel 기반 WBS 생성 및 진척 추적
- 태스크 계층: Phase → Work Package → Task
- 의존성 DAG 검증, 공수 추정

### M4: Trello (칸반 보드)

- 보드/리스트/카드 CRUD
- WBS 태스크 → 카드 동기화
- 라벨, 담당자, 마감일 관리

### M5: Dooray (태스크/주간보고)

- 주간보고 자동 작성/발송
- 회의/미팅 기록 → 액션 아이템 → 태스크 생성
- WBS/Trello 데이터 연동

### M6: Google Drive (파일 관리)

- 산출물 업/다운로드
- 문서 수정 (Docs/Sheets 연동)
- 폴더 구조 관리, 권한 설정

### M7: Datadog (모니터링)

- 모니터 생성/관리 (임계값, 알림 라우팅)
- 대시보드 생성/수정/캡처
- 메트릭 쿼리 검증

## MCP 서버

| 모듈 | MCP 서버 | 패키지 |
|------|---------|--------|
| pptx | pptx | `uvx --from office-powerpoint-mcp-server ppt_mcp_server` |
| docx | docx | `uvx --from office-word-mcp-server word_mcp_server` |
| trello | trello | `npx mcp-server-trello` |
| wbs | — | Excel 직접 조작 |
| dooray | dooray | `uvx dooray-mcp` |
| datadog | datadog | `npx @winor30/mcp-server-datadog` |
| gdrive | google-workspace | `uvx workspace-mcp` |

토글: `bash scripts/mcp-toggle.sh <server> on|off`

## 크로스 플랫폼 요구사항

- Claude Code에서 설정 변경 시 Hook(`sync-to-platforms.sh`)이 Kiro/Antigravity에 자동 동기화
- Kiro에서는 `invokeSubAgent`로 Planner/Executor/Reviewer 분리 실행
- Antigravity에서는 `AGENTS.md` + `.agent/workflows/` 활용
- 역방향 동기화 금지 (Kiro/Antigravity → Claude Code)

## 하네스 파이프라인 요구사항

기술 스펙(`specs/ai-agent-engineering-spec-2026.md`)을 기반으로 현 프로젝트에 적용한다.

### 에이전트 실행 모델

- 각 에이전트(Planner, Executor, Reviewer)는 독립 Agent_Session으로 실행 (컨텍스트 비공유)
- Claude Code: `claude --print`로 별도 프로세스 호출
- Kiro: `invokeSubAgent`로 별도 서브에이전트 호출
- 에이전트 간 통신: Handoff_File (JSON) 기반, `results/` 하위에 저장
- 모든 파일 쓰기에 Atomic_Write 패턴 적용

### Confidence_Trigger 적용

| 종합 점수 | 파이프라인 모드 | Feedback_Loop 최대 | 비고 |
|-----------|----------------|-------------------|------|
| 0.85 이상 | 단일 에이전트 | N/A | 간단한 수정, 조회 |
| 0.70-0.84 | 멀티 에이전트 (축소) | 3회 | 일반 산출물 생성 |
| 0.50-0.69 | 멀티 에이전트 (전체) | 5회 | 복잡한 산출물, 다중 모듈 |
| 0.50 미만 | 멀티 에이전트 + UltraPlan | 5회 | 대규모 작업, 아키텍처 변경 |

### 정보 차단 규칙

- Reviewer는 Executor의 reasoning을 절대 볼 수 없음
- Reviewer에게 이전 리뷰 결과를 전달하지 않음 (앵커링 방지)
- 각 에이전트는 Context_Reset 전략 적용 (클린 컨텍스트에서 시작)

### Guardian 적용

- PreToolUse Hook으로 위험 명령 사전 차단
- Pattern_Matcher 기반 (Claude API 호출 없이 즉각 차단)
- 차단 대상: `rm -rf /`, `DROP TABLE`, `DROP DATABASE`, `git push --force main`

### Sprint_Contract 구조

Planner가 생성하는 실행 계획 JSON:
```json
{
  "id": "UUID",
  "goal": "작업 목표",
  "module": "대상 모듈",
  "files": ["수정 대상 파일"],
  "acceptance_criteria": [{"id": "AC1", "description": "...", "verification_method": "tool_check"}],
  "constraints": ["제약 조건"],
  "risks": ["식별된 리스크"]
}
```

### Verdict 구조

Reviewer가 생성하는 검증 결과 JSON:
```json
{
  "verdict": "approved|needs_revision|rejected",
  "score": 0.0,
  "checklist_results": {"criterion": true},
  "issues": ["구체적 이슈"],
  "suggestions": ["개선 제안"]
}
```

### Feedback_Loop

- 리뷰 실패 시 Reviewer의 issues + suggestions를 Executor에 전달
- 최대 재시도: Confidence_Trigger 구간에 따라 3~5회
- 최소 승인 점수: 0.7/1.0
- 동일 이슈 2회 연속 발생 시 사용자에게 에스컬레이션

### KAIROS 감시 (향후 적용)

- 파일 변경 시 경량 사전 감시 (lint-level)
- Evaluator의 전체 검증과 범위 분리
- Hook 기반: `fileEdited` 이벤트로 트리거

### Auto_Dream 메모리 관리 (향후 적용)

- 7일 이상 경과한 완료 Handoff_File을 `archive/`로 이동
- 중복 엔트리 탐지 및 제거
- 파이프라인 완료 후에만 실행 (활성 실행 중 불변)

### Harness_Subtraction (향후 적용)

- 각 에이전트 컴포넌트의 기여도 메트릭 수집
- 30일간 기여도 0인 컴포넌트 비활성화 제안
- 새 모델 버전 감지 시 메트릭 리셋 및 재평가

## 참조 문서

- 기술 스펙: `specs/ai-agent-engineering-spec-2026.md` (새 기술 추가/requirements 업데이트 시에만 참조)
- PPTX 레이아웃: `modules/pptx/references/layout-spec.md`
- 모듈별 체크리스트: `skills/orchestrator/references/module-checklists.md`
