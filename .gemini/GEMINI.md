# Multi-Agent Harness — Antigravity Configuration

## 근거 기반 제안 원칙 (CRITICAL)

모든 기술적 제안은 공식 문서/블로그/스펙에 근거해야 한다. 출처 없는 임의 제안 금지.
제안 시 참조 URL 또는 문서명 필수.

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

### Step 2: Executor (v2.0 — Constraint-Aware)

Planner의 계획을 받아 실행한다. 자기 평가를 하지 않는다.
`skills/executor/SKILL.md`와 `modules/{module}/SKILL.md`를 참조한다.

**핵심 변경 (v2.0):**
- 실행 전 모든 제약 조건을 사전 확인 (Module SKILL > Sprint Contract > acceptance criteria)
- 출력에 `constraint_compliance` 필드 포함 (각 제약별 PASS/FAIL)
- 재시도 시 `retry_fixes` 필드로 이전 이슈별 근본원인 + 수정 내역 추적
- 제약 위반 액션은 실행하지 않고 `blocked_by_constraint`로 보고

### Step 3: Reviewer (v2.0 — Constraint Verification)

Executor의 결과를 **계획 + 출력만** 받아 적대적으로 검증한다.
Executor의 reasoning/의도는 전달하지 않는다.
`skills/reviewer/SKILL.md`와 `skills/orchestrator/references/module-checklists.md`를 참조한다.

**핵심 변경 (v2.0):**
- 가장 먼저 `constraint_compliance` 필드 독립 검증 (없으면 FAIL)
- 재시도 시 `retry_fixes` 필드로 이전 피드백 반영 여부 확인 (없으면 FAIL)
- 제약 위반 시 score 0.3 상한
- 출력에 `constraint_violations`, `retry_fix_assessment` 포함

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

## PPTX Module: Subtitle Rules

- 중제목 텍스트 박스 크기(width/height) 변경 금지
- 최대 2줄 허용, 단어 중간 줄바꿈 금지
- 3줄 초과 시 텍스트 요약하여 2줄로 축소

## Constraints

- Executor와 Reviewer를 하나의 에이전트로 합치지 말 것
- Executor reasoning을 Reviewer에 전달하지 말 것
- 리뷰 단계를 생략하지 말 것
- Module SKILL 디자인 규칙을 위반하지 말 것 (예: 텍스트 박스 크기 변경 금지)
- 설정 흐름: Claude Code → Kiro/Antigravity (역방향 금지)
