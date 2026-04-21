# Run Multi-Agent Pipeline

모듈 작업 요청 시 반드시 아래 3단계를 별도 컨텍스트로 분리 실행한다.

## Step 1: Planner

참조: `skills/planner/SKILL.md`, `modules/{module}/SKILL.md`

작업 요구사항을 분석하고 구조화된 실행 계획(JSON)을 생성한다.
계획에는 acceptance_criteria, constraints, risks를 포함한다.
결과를 `results/{module}/plan-{name}.json`에 저장한다.

## Step 2: Executor

참조: `skills/executor/SKILL.md`, `modules/{module}/SKILL.md`

Planner의 계획을 받아 실행한다.
자기 평가를 하지 않는다. 결과만 출력한다.

## Step 3: Reviewer

참조: `skills/reviewer/SKILL.md`, `skills/orchestrator/references/module-checklists.md`

Executor의 결과를 계획 + 출력만 받아 적대적으로 검증한다.
Executor의 reasoning/의도는 전달하지 않는다.
결과를 `results/{module}/review-{name}.json`에 저장한다.

## Step 4: 재시도 또는 완료

- APPROVED (score >= 0.7): 결과 반환
- NEEDS_REVISION: Reviewer 이슈를 Executor에 피드백하여 Step 2 재실행
- 최대 재시도: Confidence_Trigger 구간에 따라 3~5회
- 최대 재시도 소진: 전체 이력과 함께 사용자에게 에스컬레이션

## Shell 실행 (대안)

```bash
bash scripts/orchestrate.sh "<task>" <module>
bash scripts/orchestrate.sh "<task>" "mod1,mod2"  # Agent_Team
```

## 정보 차단 규칙

- Reviewer에게 Executor의 reasoning을 전달하지 않는다
- Reviewer에게 이전 리뷰 결과를 전달하지 않는다 (앵커링 방지)
- 각 단계는 독립된 컨텍스트에서 실행한다

## Available Modules

pptx, docx, wbs, trello, dooray, datadog, google_workspace
