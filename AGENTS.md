# Multi-Agent Harness — Universal Agent Instructions

## 근거 기반 제안 원칙 (CRITICAL)

모든 기술적 제안은 공식 문서/블로그/스펙에 근거해야 한다. 출처 없는 임의 제안 금지.
제안 시 참조 URL 또는 문서명 필수. 적용 범위: 파이프라인, 클라우드, MCP, 크로스 플랫폼 sync 전체.

## Role

You are part of a multi-agent adversarial review pipeline (v3: Subagents Native).

## Critical Rules

1. **Harness Mandatory**: ALL module tasks (pptx, docx, wbs, trello, dooray, google_workspace, datadog) MUST go through the harness pipeline. Single-agent direct execution is FORBIDDEN.
2. **Role Isolation**: Each agent (Planner, Executor, Reviewer) operates independently — Executor/Reviewer receives only its own step info, never the full Sprint_Contract
3. **Information Barrier**: The Reviewer MUST NOT see Executor's reasoning — only plan + output
4. **No Self-Review**: The agent that produces output NEVER evaluates its own work
5. **Parallel Execution**: Executors and Reviewers spawn in parallel per dependency level — sequential switch without user approval is FORBIDDEN
6. **MCP First**: New content (shapes/textboxes/images) must use MCP tools only — no direct python-pptx creation
7. **Retry with Feedback**: On review failure, Executor receives specific issues. Max 5 retries, approved steps skipped.

## Pipeline Flow (v3: Subagents Native)

```
1. @planner → Sprint_Contract JSON (sequential, once)
2. Analyze dependency levels in Sprint_Contract
3. level 0 steps → spawn executor subagents in parallel
4. level 1+ steps → spawn after previous level completes
5. All executors done → spawn reviewer subagents in parallel
6. Failed steps retry (max 5). Approved steps skip.
7. Report token usage table per stage.
```

## Subagent Definitions (.claude/agents/)

| File | Role | MCP | Model |
|------|------|-----|-------|
| `planner.md` | Sprint_Contract JSON | none | sonnet |
| `executor.md` | pptx execution | pptx (inline) | sonnet |
| `executor-docx.md` | docx execution | docx (inline) | sonnet |
| `executor-dooray.md` | dooray execution | dooray (inline) | sonnet |
| `executor-google_workspace.md` | google_workspace execution | google-workspace (inline) | sonnet |
| `reviewer-google_workspace.md` | google_workspace API verification | google-workspace (inline) | sonnet |
| `reviewer.md` | adversarial review | Bash + Read | sonnet |

## recon step 자동 분기

| 조건 | 모드 |
|------|------|
| `contract.mode == "create"` 또는 생성/new 키워드 | Create — recon 건너뜀 |
| 수정/fix/update 키워드 또는 steps에 recon 존재 | Modify — recon 정상 실행 |

## Cross-Platform

Configuration flow is one-way: Claude Code → Kiro/Antigravity (never reverse).

| Platform | Config | Entry |
|----------|--------|-------|
| Claude Code (Primary) | `CLAUDE.md` + `.claude/agents/*.md` | Orchestrator = this session |
| Kiro (Sync) | `AGENTS.md` + `.kiro/steering/` | `invokeSubAgent` |
| Antigravity (Sync) | `AGENTS.md` + `.gemini/GEMINI.md` | Workflow: `/run-pipeline` |

Sync: `bash scripts/agents/sync_pipeline.sh --from claude_code --to all`

## Executor: Constraint-Aware Execution

실행 전 모든 제약 조건 확인. 출력에 `constraint_compliance` 필드 포함 필수.
재시도 시 `retry_fixes` 필드로 이전 이슈별 수정 내역 추적.
**제약 우선순위**: Module SKILL > Sprint Contract constraints > acceptance criteria > 자체 판단

## Reviewer: Constraint Verification

`constraint_compliance` 필드 독립 검증 우선 (없으면 FAIL).
재시도 시 `retry_fixes` 반영 여부 확인 (없으면 FAIL).
제약 위반 시 score 0.3 상한.

## 모듈별 규칙

모듈 작업 시 해당 `modules/<module>/SKILL.md`를 반드시 읽는다. 모듈별 실행 규칙(MCP 사용법, 검증 절차, 직접실행 기준 등)은 루트가 아닌 모듈 디렉토리에 있다.

| 모듈 | 규칙 파일 |
|------|---------|
| pptx | `modules/pptx/SKILL.md` + `modules/pptx/MISTAKES.md` |
| docx | `modules/docx/SKILL.md` (예정) |
| dooray | `modules/dooray/SKILL.md` (예정) |
