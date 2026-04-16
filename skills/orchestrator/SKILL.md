---
name: orchestrator
description: >
  Controls the multi-agent pipeline with adversarial review loop.
  v3: Claude session IS the Orchestrator — uses subagents natively via @-mention.
  Routes tasks between Planner, Executor, and Reviewer subagents.
  Triggers on "run pipeline", "orchestrate task", "start workflow", "process request".
metadata:
  author: harness-team
  version: 3.0.0
  role: orchestrator
  category: workflow-automation
  architecture: subagents_native
---

# Orchestrator — Subagents Native (v3)

## Architecture

`[공식]` code.claude.com/docs/en/sub-agents.md

```
v1: bash orchestrate.sh → claude --print subprocess (Python 병렬화)
v2: bash orchestrate.sh → Agent tool (run_in_background)
v3: Claude session = Orchestrator → @-mention subagents directly
```

## Pipeline Flow

```
User Request
    │
    ▼
Claude Session (Orchestrator)
    │
    ├─ @planner → Sprint_Contract JSON (순차 1회)
    │
    ├─ @executor × N (병렬 — dependency level 0)
    ├─ @executor × M (병렬 — dependency level 1, level 0 완료 후)
    │
    ├─ @reviewer × N (병렬 — 전체 executor 완료 후)
    │
    └─ 실패 step만 재시도 (approved step 스킵, max 5회)
```

## Step 1: Plan

```
@planner "Task: <task>
Module: <module>
스키마: schemas/sprint_contract.schema.json"
```

- Planner는 Sprint_Contract JSON만 출력 (tools: [])
- 결과를 `.pipeline/<timestamp>/sprint_contract.json`에 저장

## Step 2: Execute (병렬)

Sprint_Contract의 dependency 분석 후 level별로 executor 병렬 spawn:

```
# level 0 (동시 실행)
@executor "STEP 1: <action>, acceptance_criteria: [...], constraints: [...]"
@executor "STEP 2: <action>, acceptance_criteria: [...], constraints: [...]"

# level 1 (level 0 완료 후 동시 실행)
@executor "STEP 4: merge — /tmp/slide_*.pptx → results/pptx/output.pptx"
```

**각 Executor는 자기 step 정보만 수신:**
- TASK, MODULE (최소 컨텍스트)
- 해당 step의 action, acceptance_criteria, constraints
- 의존 step 결과 요약 (필요 시)
- MCP는 executor subagent의 mcpServers에서 자동 연결/해제

## Step 3: Review (병렬)

```
@reviewer "STEP 1 검증: action=..., acceptance_criteria=..., output_file=.pipeline/.../step_1_output.json"
@reviewer "STEP 2 검증: action=..., acceptance_criteria=..., output_file=.pipeline/.../step_2_output.json"
```

**Information Isolation:**
- Reviewer는 해당 step의 Sprint_Contract 정보 + 실행 결과만 수신
- Executor reasoning 미포함

## Step 4: Verdict & Retry

- `approved` (score >= 0.85, constraint_violations 없음): 해당 step 완료
- `needs_revision`: 해당 step만 재시도 (max 5회)
- 연속 2회 동일 issues → escalate (사용자 리뷰 요청)

## 파일 구조

```
.pipeline/<timestamp>/
  sprint_contract.json
  step_1_output.json
  step_2_output.json
  review_1_step_1_verdict.json
  review_1_step_2_verdict.json
  summary.json
```
