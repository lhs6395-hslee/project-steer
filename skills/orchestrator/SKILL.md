---
name: orchestrator
description: >
  Controls the multi-agent pipeline with adversarial review loop.
  v2: Uses Claude Code native Agent tool (.claude/agents/) instead of claude --print.
  Routes messages between Planner, Executor, and Reviewer subagents.
  Triggers on "run pipeline", "orchestrate task", "start workflow", "process request".
metadata:
  author: harness-team
  version: 2.0.0
  role: orchestrator
  category: workflow-automation
  architecture: agent_tool_native
---

# Orchestrator — Agent Tool Native (v2)

## Architecture

v1 (`claude --print` subprocess) → v2 (Claude Code Agent tool)

**공식 문서 근거:**
- Subagent definitions: `code.claude.com/docs/en/agent-sdk/subagents.md`
- Agent tool frontmatter: `.claude/agents/*.md`
- Structured outputs: `code.claude.com/docs/en/agent-sdk/structured-outputs.md`

## Pipeline Flow

```
User Request
    │
    ▼
bash scripts/orchestrate.sh  ← Confidence_Trigger + pipeline_config.json 생성
    │
    ▼
Claude Code Session (Agent tool native)
    │
    ├─ Agent(subagent_type="planner") → Sprint_Contract JSON
    │
    ├─ Agent(subagent_type="executor") → Execution output (MCP tools 사용)
    │
    ├─ Agent(subagent_type="reviewer") → Verdict JSON (information isolated)
    │
    └─ Retry loop (verdict != approved && attempt < max_retries)
```

## Step 1: Initialize Pipeline

```bash
bash scripts/orchestrate.sh "<task>" <module>
```

이 스크립트는:
1. 모듈 유효성 검증
2. Confidence_Trigger 실행 → mode/max_retries/ultraplan 결정
3. `pipeline_config.json` 생성 (Agent tool 호출 설정)

## Step 2: Plan Phase (Agent Tool)

Claude Code 세션에서 Agent tool로 @planner subagent 호출:

```
Agent({
  description: "Plan: <task>",
  subagent_type: "planner",
  model: "sonnet",
  prompt: "Task: <task>\nModule: <module>\n\n<module SKILL content>\n\nGenerate Sprint_Contract JSON."
})
```

**Planner 특성** (`.claude/agents/planner.md`):
- `tools: []` — 도구 없음, 순수 JSON 출력
- `model: sonnet` — 빠르고 안정적
- 출력: `schemas/sprint_contract.schema.json` 준수

## Step 3: Execute-Review Loop (Agent Tool)

### 3a. Executor

```
Agent({
  description: "Execute: <task>",
  subagent_type: "executor",
  model: "sonnet",
  prompt: "SPRINT_CONTRACT:\n<plan JSON>\n\n<module SKILL>\n\nExecute and produce output JSON."
})
```

**Executor 특성** (`.claude/agents/executor.md`):
- `permissionMode: bypassPermissions` — MCP 도구 자동 승인
- MCP 서버 접근 가능 (pptx, dooray 등)
- 출력: 구조화된 실행 결과 JSON

### 3b. Reviewer (Information Isolated)

```
Agent({
  description: "Review: <task>",
  subagent_type: "reviewer",
  model: "sonnet",
  prompt: "SPRINT_CONTRACT:\n<plan JSON>\n\nEXECUTION OUTPUT:\n<exec output>\n\nReview adversarially."
})
```

**Reviewer 특성** (`.claude/agents/reviewer.md`):
- `tools: []` — 도구 없음, 순수 JSON 출력
- Information barrier: Executor reasoning 미포함
- 출력: `schemas/verdict.schema.json` 준수

### 3c. Verdict Evaluation

- `approved` (score >= 0.7): 파이프라인 성공
- `needs_revision`: issues/suggestions를 Executor에 피드백, 재시도
- `rejected`: 재시도 남으면 루프, 없으면 실패

### 3d. Circular Feedback Detection

연속 2회 동일 issues → escalate (사람 리뷰)

## Step 4: Save Results

각 단계의 JSON을 `$RUN_DIR/`에 저장:
- `sprint_contract.json`
- `exec_output_{attempt}.json`
- `verdict_{attempt}.json`
- `summary.json`

## Information Isolation Rules

Reviewer는 오직 다음만 수신:
- Sprint_Contract (Planner 출력)
- Execution output (Executor 출력)

Reviewer는 절대 수신하지 않음:
- Executor의 내부 reasoning/intent
- Executor의 self-assessment
- 이전 review 결과 (anchoring bias 방지)

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| max_retries | 3-5 | Confidence_Trigger 구간에 따라 결정 |
| min_score | 0.7 | 승인 최소 점수 |
| model | sonnet | 모든 subagent 기본 모델 |

## v1 → v2 Migration

| v1 (claude --print) | v2 (Agent tool) | 공식 근거 |
|---------------------|-----------------|----------|
| `claude --print --bare` | `Agent(subagent_type=...)` | subagents.md |
| `extract_result.py` JSON 래퍼 | Agent tool 직접 반환 | structured-outputs.md |
| `orchestrate.sh` 단일 프로세스 | `pipeline_config.json` + 세션 내 Agent tool | agent-sdk/overview.md |
| `call_agent.sh` 필수 | CLI fallback only (non-Claude-Code 환경) | cli-reference.md |
