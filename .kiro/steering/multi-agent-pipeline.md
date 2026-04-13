---
inclusion: auto
---

# Multi-Agent Adversarial Review Pipeline

이 프로젝트는 하네스 엔지니어링 기반 멀티 에이전트 파이프라인이다.
모든 작업은 반드시 Planner → Executor → Reviewer 순서로 수행한다.

## 필수 실행 규칙 (CRITICAL)

모듈 작업(pptx, docx, wbs, trello, dooray, gdrive, datadog)은 반드시 하네스 파이프라인으로 실행한다.
싱글 에이전트로 직접 수행하는 것은 금지한다.
"간단한 작업"이라도 예외 없이 아래 3단계를 invokeSubAgent로 분리 실행한다.

1. requirements.md를 읽고 Confidence_Trigger 점수를 산출한다
2. 점수에 따라 파이프라인 모드를 결정한다
3. Planner → Executor → Reviewer 순서로 서브에이전트 호출

작업 요청을 받으면 반드시 아래 3단계를 invokeSubAgent로 분리 실행한다.

### Step 1: Planner (서브에이전트 호출)

invokeSubAgent로 general-task-execution 에이전트를 호출한다.
프롬프트에 skills/planner/SKILL.md의 지침을 포함하고,
구조화된 실행 계획(JSON)을 생성하도록 지시한다.

```
invokeSubAgent:
  name: general-task-execution
  prompt: |
    당신은 Planner 에이전트입니다.
    skills/planner/SKILL.md의 지침에 따라 아래 작업의 실행 계획을 JSON으로 생성하세요.
    작업: {사용자 요청}
    모듈: {대상 모듈}
  contextFiles: [skills/planner/SKILL.md, modules/{module}/SKILL.md]
```

### Step 2: Executor (서브에이전트 호출)

Planner의 계획을 받아 invokeSubAgent로 실행한다.
Executor는 계획대로만 실행하고 자기 평가를 하지 않는다.

```
invokeSubAgent:
  name: general-task-execution
  prompt: |
    당신은 Executor 에이전트입니다.
    skills/executor/SKILL.md의 지침에 따라 아래 계획을 실행하세요.
    계획: {Planner 출력}
    자기 평가는 하지 마세요. 결과만 출력하세요.
  contextFiles: [skills/executor/SKILL.md, modules/{module}/SKILL.md]
```

### Step 3: Reviewer (서브에이전트 호출)

Executor의 결과를 받아 invokeSubAgent로 독립 검증한다.
Reviewer는 계획 + 결과만 받고, Executor의 reasoning은 받지 않는다.

```
invokeSubAgent:
  name: general-task-execution
  prompt: |
    당신은 Reviewer 에이전트입니다.
    skills/reviewer/SKILL.md의 지침에 따라 적대적으로 검증하세요.
    계획: {Planner 출력}
    실행 결과: {Executor 출력}
    Executor의 의도나 reasoning은 제공되지 않습니다.
    체크리스트 평가, 점수(0.0~1.0), 판정(approved/needs_revision/rejected)을 출력하세요.
  contextFiles: [skills/reviewer/SKILL.md, skills/orchestrator/references/module-checklists.md]
```

### Step 4: 재시도 또는 완료

- APPROVED (score >= 0.7): 결과 반환
- NEEDS_REVISION: Reviewer의 이슈를 Executor에 피드백하여 Step 2 재실행 (최대 3회)
- 3회 실패: 전체 이력과 함께 사용자에게 에스컬레이션

## 정보 차단 규칙

- Reviewer에게 Executor의 reasoning/의도를 전달하지 않는다
- Reviewer에게 이전 리뷰 결과를 전달하지 않는다 (앵커링 방지)
- 각 서브에이전트는 독립된 컨텍스트에서 실행된다

## MCP 서버 토글

작업 시작 전 필요한 MCP 서버만 켠다:
```bash
bash scripts/mcp-toggle.sh <server> on
```
작업 완료 후 끈다:
```bash
bash scripts/mcp-toggle.sh <server> off
```

## 모듈-MCP 매핑

- pptx → pptx
- docx → docx
- trello → trello
- dooray → dooray
- datadog → datadog
- gdrive → google-workspace

## 설정 흐름

Claude Code (.mcp.json) → Kiro (.kiro/settings/mcp.json) 단방향.
역방향 금지.
