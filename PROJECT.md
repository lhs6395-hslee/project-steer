# Project-Steer 요구사항 문서

## 프로젝트 개요

하네스 엔지니어링 기반 멀티 에이전트 파이프라인으로, 7개 업무 모듈(pptx, docx, wbs, trello, dooray, google_workspace, datadog)의 산출물을 자동 생성·검증한다.

기술 스펙 레퍼런스: `specs/ai-agent-engineering-spec-2026.md`

## 아키텍처

- Primary: Claude Code (v3: Subagents Native — `.claude/agents/` subagent definitions, @-mention 직접 호출)
- Sync: Kiro (`.kiro/steering/`, `.kiro/hooks/`, `invokeSubAgent`), Antigravity (`.gemini/`, `.agent/`)
- 설정 흐름: Claude Code → Kiro/Antigravity (단방향)

## 에이전트 역할

| 에이전트 | 정의 파일 | 역할 |
|---------|----------|------|
| Planner | `.claude/agents/planner.md` | 요구사항 분석, 실행 계획 생성 |
| Executor | `.claude/agents/executor.md` | 계획 실행, 산출물 생성 |
| Reviewer | `.claude/agents/reviewer.md` | 적대적 독립 검증 |
| Orchestrator | `skills/orchestrator/SKILL.md` | 파이프라인 제어, 재시도 루프 |

## 모듈 요구사항

### M1: PPTX (프레젠테이션)

세부 실행 규칙: `modules/pptx/SKILL.md` | 재발 방지: `modules/pptx/MISTAKES.md`

- 생성 옵션: Option 1 (MCP 직접), Option 2 (template zipfile), Option 3 (layout_intro zipfile)
- 템플릿: `modules/pptx/templates/pptx_template.pptx`, `pptx_layout_intro.pptx`
- 레이아웃 스펙: `modules/pptx/references/layout-spec.md` (L01~L36 + Thank You)
- 슬라이드 구조: 표지 → 목차 → 본문 → 끝맺음

### M2: DOCX (문서)

- 스타일 가이드: `modules/docx/templates/docx_style_guide.md`
- 템플릿: `modules/docx/templates/docx_template.docx`
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
| google_workspace | google-workspace | `uvx workspace-mcp` |

토글: executor subagent의 `mcpServers` inline 정의로 자동 연결/해제

## 크로스 플랫폼 요구사항

- Sync는 코드 동기화가 아니라 **파이프라인 동작 방식의 동기화**
- 각 IDE에서 Planner→Executor→Reviewer 역할 분리가 동일하게 동작해야 함
- Claude Code에서 설정 변경 시 Hook(`sync-to-platforms.sh`)이 Kiro/Antigravity에 자동 동기화
- Kiro에서는 메인이 Planner+Executor 직접 수행, `invokeSubAgent`로 Reviewer만 분리 (속도 최적화 + 확증편향 방지)
- Antigravity에서는 `.gemini/GEMINI.md` Step 1/2/3 + `.agent/workflows/run-pipeline.md`로 3단계 별도 컨텍스트 실행
- VS Code에서는 Claude 세션이 Orchestrator — @planner/@executor/@reviewer 직접 호출
- 역방향 동기화 금지 (Kiro/Antigravity → Claude Code)

## 하네스 파이프라인 요구사항

기술 스펙(`specs/ai-agent-engineering-spec-2026.md`)을 기반으로 현 프로젝트에 적용한다.

### 에이전트 실행 모델

- 각 에이전트(Planner, Executor, Reviewer)는 독립 Agent_Session으로 실행 (컨텍스트 비공유)
- Claude Code: v3 Subagents Native (`.claude/agents/` subagent definitions) — `claude --print` v1, run_in_background v2 방식 사용 안 함
- Kiro: `invokeSubAgent`로 별도 서브에이전트 호출
- 에이전트 간 통신: Agent tool 구조화 출력 — Handoff_File 파일 교환은 v1 레거시
- 모든 파일 쓰기에 Atomic_Write 패턴 적용

### 정보 차단 규칙

- Reviewer는 Executor의 reasoning을 절대 볼 수 없음
- Reviewer에게 이전 리뷰 결과를 전달하지 않음 (앵커링 방지)
- 각 에이전트는 Context_Reset 전략 적용 (클린 컨텍스트에서 시작)

### Guardian 적용

- PreToolUse Hook으로 위험 명령 사전 차단
- Pattern_Matcher 기반 (Claude API 호출 없이 즉각 차단)
- 차단 대상: `rm -rf /`, `DROP TABLE`, `DROP DATABASE`, `git push --force main`

### Sprint_Contract 구조

Planner가 생성하는 실행 계획 JSON (`schemas/sprint_contract.schema.json`):
```json
{
  "task": "작업 목표",
  "module": "pptx|docx|wbs|trello|dooray|google_workspace|datadog",
  "mode": "create|modify",
  "recon_step_id": 1,
  "steps": [
    {
      "id": 1,
      "action": "Slide 7 (L02): subtitle 수정 — /tmp/slide_7.pptx",
      "dependencies": [],
      "acceptance_criteria": ["측정 가능한 기준"],
      "estimated_complexity": "low|medium|high",
      "constraints": ["해당 step 관련 제약만"],
      "target_slide_index": 6
    }
  ],
  "acceptance_criteria": ["전체 완료 기준"],
  "risks": [{"id": "R1", "description": "...", "likelihood": "low", "impact": "low", "mitigation": "..."}]
}
```

### Verdict 구조

Reviewer가 생성하는 검증 결과 JSON (`schemas/verdict.schema.json`):
```json
{
  "verdict": "approved|needs_revision|rejected",
  "score": 0.0,
  "checklist_results": {
    "completeness": true,
    "constraint_compliance": true,
    "content_accuracy": true,
    "design_quality": true
  },
  "constraint_violations": [{"constraint": "...", "violation": "...", "severity": "critical|major|minor"}],
  "issues": ["구체적 이슈"],
  "suggestions": ["개선 제안"],
  "retry_fix_assessment": [{"original_issue": "...", "fixed": true}]
}
```

### Feedback_Loop

- 리뷰 실패 시 Reviewer의 issues + suggestions를 Executor에 전달
- 최대 재시도: 5회
- 최소 승인 점수: 0.85/1.0
- 동일 이슈 2회 연속 발생 시 사용자에게 에스컬레이션

### KAIROS 감시

- 스크립트: `scripts/agents/kairos.sh`
- 파일 변경 시 경량 사전 감시 (lint-level)
- Evaluator의 전체 검증과 범위 분리
- PostToolUse Hook에서 자동 호출

## 참조 문서

- 기술 스펙: `specs/ai-agent-engineering-spec-2026.md`
- PPTX 레이아웃: `modules/pptx/references/layout-spec.md`
- 모듈별 체크리스트: `skills/orchestrator/references/module-checklists.md`
