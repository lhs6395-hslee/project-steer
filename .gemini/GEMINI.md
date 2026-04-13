# Multi-Agent Harness — Antigravity Configuration

## Project Context

하네스 엔지니어링 기반 멀티 에이전트 파이프라인. 23개 요구사항 구현.
에이전트는 SKILL.md 파일로 정의, 스크립트는 `scripts/agents/`에 위치.

## Standards

- 모든 모듈 작업은 하네스 파이프라인 필수 (싱글 에이전트 금지)
- Confidence_Trigger로 파이프라인 모드 결정
- Guardian으로 위험 명령 사전 차단
- Reviewer는 Executor의 reasoning을 볼 수 없음
- 모든 파일 쓰기에 Atomic_Write 패턴

## Pipeline Execution (역할 분리 필수)

모듈 작업 요청 시 반드시 아래 3단계를 **별도 컨텍스트**로 분리 실행한다.
"간단한 작업"이라도 예외 없이 3단계를 거친다.

### Step 1: Planner

`skills/planner/SKILL.md`와 `modules/{module}/SKILL.md`를 참조하여 구조화된 실행 계획(JSON)을 생성한다.
계획에는 acceptance_criteria, constraints, risks를 포함한다.

### Step 2: Executor

Planner의 계획을 받아 실행한다. 자기 평가를 하지 않는다.
`skills/executor/SKILL.md`와 `modules/{module}/SKILL.md`를 참조한다.

### Step 3: Reviewer

Executor의 결과를 **계획 + 출력만** 받아 적대적으로 검증한다.
Executor의 reasoning/의도는 전달하지 않는다.
`skills/reviewer/SKILL.md`와 `skills/orchestrator/references/module-checklists.md`를 참조한다.

### Step 4: 재시도 또는 완료

- APPROVED (score >= 0.7): 결과 반환
- NEEDS_REVISION: Reviewer 이슈를 Executor에 피드백하여 Step 2 재실행
- 최대 재시도: Confidence_Trigger 구간에 따라 3~5회

## Shell Pipeline (대안)

```bash
bash scripts/orchestrate.sh "<task>" <module>
bash scripts/orchestrate.sh "<task>" "mod1,mod2"  # Agent_Team
```

## Agent Scripts

orchestrate.sh, call_agent.sh, confidence_trigger.sh, guardian.sh,
ide_adapter.sh, kairos.sh, auto_dream.sh, ultraplan.sh, token_tracker.sh,
harness_subtraction.sh, agent_team.sh, git_worktree.sh, sdd_integrator.sh,
sync_pipeline.sh, mcp-toggle.sh

## Schemas

- `schemas/sprint_contract.schema.json` — Planner 출력
- `schemas/verdict.schema.json` — Reviewer 출력
- `schemas/handoff_file.schema.json` — 에이전트 간 통신

## Module Skills

`modules/{name}/SKILL.md`: pptx, docx, wbs, trello, dooray, gdrive, datadog

## Constraints

- Executor와 Reviewer를 하나의 에이전트로 합치지 말 것
- Executor reasoning을 Reviewer에 전달하지 말 것
- 리뷰 단계를 생략하지 말 것
- 설정 흐름: Claude Code → Kiro/Antigravity (역방향 금지)
