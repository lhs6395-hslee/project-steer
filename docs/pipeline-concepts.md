# Pipeline 개념 아카이브

에이전트 정의 파일(.claude/agents/)에는 넣지 않는 개념 설명 모음.
컨텍스트 소비 없이 인간이 참조하는 용도.

---

## recon step

**정의**: 수정(Modify) 작업에서만 사용하는 사전 측정 step.
python-pptx로 기존 PPTX를 직접 열어 각 shape의 실측값을 기록하고 문제 항목을 파악한다.

**수정 작업에서 필요한 이유**
어떤 shape이 잘못됐는지(subtitle 3줄, 아이콘 위치 오류 등)를 측정해야
이후 step들이 정확히 수정할 수 있음.

**신규 생성 작업에서는 불필요**
템플릿에서 시작하므로 측정할 기존 상태가 없음 → Pattern A에는 recon 없음.

**위치**: 항상 step1, `dependencies: []`
결과를 다른 step들이 의존하므로 먼저 완료돼야 함 (step2~N은 dep: [1]).

**출력 원칙**: 문제 항목만 명시. 정상 항목 나열 금지 (context 낭비).

---

## 파이프라인 전체 흐름

```
[Planner] 전체 슬라이드 구조 설계 (순차, 1회)
    → Sprint_Contract 생성
    ↓
[Pattern A: 신규 생성]
  step1~N-1: 슬라이드별 생성 (완전 병렬, dependency: [])
  stepN: merge (step1~N-1 완료 후)

[Pattern B: 수정]
  step1: recon (순차, dependency: [])
  step2~N-1: 슬라이드별 수정 (완전 병렬, dependency: [1])
  stepN: merge (step2~N-1 완료 후)
    ↓
[Reviewer] 슬라이드별 병렬 검증 (완전 병렬)
    ↓
실패한 슬라이드만 재실행 → 재검증
approved 슬라이드는 스킵 (load_approved_steps)
    ↓
전체 통과 → 완료
```

---

## ~~알람 / 백그라운드~~ [LEGACY — v2, 삭제됨]

> **v3에서는 사용하지 않음.** orchestrate.sh 및 run_in_background 패턴은 v2에서 제거됨.
> v3는 Orchestrator(Claude 세션)가 @planner/@executor/@reviewer를 직접 @-mention으로 호출한다.

## Agent Teams 전환 사이드이펙트 분석 (2026-04-16)

### 결론

`[공식]` code.claude.com/docs/en/agent-teams.md — "Experimental (disabled by default)"
현 시점 전환 불가. GA 이후 재검토.

### 치명적 블로커

**per-step retry 불가**
`[공식]` agent-teams.md — 네이티브 체크포인트/승인 메커니즘 없음.
현재 `load_approved_steps()`는 `review_{ATTEMPT}_step_{STEP_ID}_verdict.json` 파일 glob으로 동작.
Agent Teams에서는 외부 state store(DB/Redis) 없이 구현 불가.

**verdict 라우팅 불가**
`[공식]` subagents.md — "Subagents cannot spawn their own subagents."
step N의 verdict를 step N executor에만 라우팅하는 메커니즘 없음.
Planner가 Executor/Reviewer를 모두 직접 spawn해야 하며 step별 격리 보장 불가.

**상태 관리 소실**
`[공식]` agent-teams.md — 팀 실행 중 상태는 에이전트 메모리에만 존재.
RUN_DIR 파일 구조 전체(`verdict_N.json`, `pipeline_status.json`, `aggregated_output.json`)가 외부 state store 없이는 재현 불가.

### 중간 난이도 (해결 가능하나 재작성 필요)

| 항목 | 현재 | Agent Teams |
|------|------|-------------|
| DAG 의존성 | `analyze_dependencies()` Python 구현 | `[추측]` 내장 없음, 직접 구현 필요 |
| 정보 격리 | 파일 경로 자체가 경계 | `[추측]` 프롬프트로만 강제, 위반 위험 |
| MCP 접근 제어 | subprocess별 `--mcp-config` | `[추측]` 팀 레벨 설정, granularity 불명 |
| 파일 아티팩트 | 공유 /tmp, results/ | `[추측]` 분산 실행 시 공유 불가 |

## 아키텍처 전환 이력 (2026-04-16)

### v1 → v2 → v3 전환 이유

#### v1: `claude --print` subprocess (Python 병렬화)

```
bash orchestrate.sh → parallel_executor.py (ThreadPoolExecutor) → call_agent.sh → claude --print
```

**문제점:**
- `claude --print`는 `[공식]` headless.md — "CI/CD, 단발성 스크립트 용도"로 분류. 멀티 에이전트 파이프라인용으로 권장하지 않음
- Python(`parallel_executor.py`, `parallel_reviewer.py`, `call_agent.sh`) 코드로 병렬화/DAG/재시도를 직접 구현 → 유지 비용 높음
- MCP 서버를 `--mcp-config` 플래그로 subprocess마다 수동 전달 → `mcp-toggle.sh` 별도 관리 필요
- 포그라운드 블로킹 → 실행 중 사용자와 대화 불가

#### v2: Agent tool + run_in_background (과도기)

```
bash orchestrate.sh (초기화) → Agent tool run_in_background=True → 세션 즉시 복귀
```

**개선:** 비블로킹 실행, 완료 시 자동 알람
**문제:** orchestrate.sh + Python 스크립트 구조 그대로 유지 — 근본 해결 아님

#### v3: Subagents Native (현재)

```
Claude Session (Orchestrator) → @planner / @executor / @reviewer 직접 호출
```

**개선:**
- `[공식]` code.claude.com/docs/en/sub-agents.md — "Run parallel research: spawn multiple subagents simultaneously"
- `[공식]` code.claude.com/docs/en/sub-agents.md — "mcpServers inline: connected when subagent starts, disconnected when it finishes"
- Python 병렬화 코드 전체 제거 (`parallel_executor.py`, `parallel_reviewer.py`, `call_agent.sh`)
- MCP 서버가 executor subagent 정의에 내장 → `mcp-toggle.sh` 불필요
- DAG/재시도/circular feedback 감지 → Orchestrator(Claude 세션)가 직접 처리

**제거된 파일:**
- `scripts/orchestrate.sh`, `scripts/mcp-toggle.sh`
- `scripts/agents/call_agent.sh`, `parallel_executor.py`, `parallel_reviewer.py`
- `scripts/agents/confidence_trigger.sh`, `ultraplan.sh`, `token_tracker.sh`
- `scripts/agents/ide_adapter.sh`, `harness_subtraction.sh`, `sdd_integrator.sh`
- `scripts/agents/agent_team.sh`, `auto_dream.sh`, `git_worktree.sh`

**유지된 파일:**
- `scripts/agents/guardian.sh` — `PreToolUse(Bash)` Hook
- `scripts/agents/kairos.sh` — `PostToolUse(Edit|Write)` Hook
- `scripts/agents/sync_pipeline.sh` — IDE 동기화

### 다음 단계: Agent Teams (예정)

`[공식]` code.claude.com/docs/en/agent-teams.md — "Experimental (disabled by default)" (2026-04-16 기준)

Agent Teams GA 이후 전환 예정. Subagents와의 차이:
- Subagents: 단일 세션 내, Orchestrator가 모든 spawn 담당
- Agent Teams: 독립 세션 간 직접 통신, 더 강한 병렬성

---

## recon step — Create/Modify 자동 분기 (2026-04-16 구현)

### 왜 Orchestrator가 판단하는가 (v3 기준)

v1에서는 `parallel_executor.py` 코드가 자동 판별했으나, v3에서는 해당 파이프라인 코드가 제거됨.
v3에서는 Orchestrator(Claude 세션)가 Sprint_Contract 수신 후 직접 판별한다.

### 판별 로직 (우선순위 순)

1. `contract.mode == "create"` → Create
2. task 키워드: '생성'/'만들'/'create'/'new'/'새로'/'신규' → Create
3. task 키워드: '수정'/'고쳐'/'변경'/'modify'/'fix'/'update' → Modify
4. steps에 recon step 존재 여부 → Planner 의도 존중 (있으면 Modify)

### 동작

- Create 모드: recon step이 있어도 실행하지 않고 건너뜀 (dependency 자동 해제)
- Modify 모드: recon step 정상 실행 → 완료 후 다음 level steps 병렬 시작

---

## 파이프라인 실행 방식 (v3 — 백그라운드 + 알람)

### 실행 모델

`[공식]` Agent tool `run_in_background=True` — subagent가 백그라운드에서 실행되며 완료 시 자동 알람.

- Executor/Reviewer는 **병렬** spawn — 각 subagent가 독립 백그라운드로 실행
- 각 subagent 완료 시 즉시 토큰 보고: `✅ [Executor] STEP N input: N, output: N tokens`
- 전체 파이프라인 완료 시 합산 테이블 출력

### 토큰 보고 형식

각 단계 완료 시:
```
✅ [Planner] input: 12,450, output: 3,210 tokens
✅ [Executor] STEP 2 input: 8,200, output: 5,100 tokens
✅ [Reviewer] STEP 2 input: 6,300, output: 1,800 tokens
```

파이프라인 완료 시:
```
| 단계              | input tokens | output tokens | 소계   |
|------------------|-------------|---------------|--------|
| Planner          | 12,450      | 3,210         | 15,660 |
| Executor (전체)  | 24,600      | 15,300        | 39,900 |
| Reviewer (전체)  | 18,900      | 5,400         | 24,300 |
| 합계             | 55,950      | 23,910        | 79,860 |
```

usage 필드가 없을 경우 해당 셀 N/A 표기.

---

## Reviewer 에이전트 구조 (reviewer.md)

### 검증 방식

독립 subagent로 실행 — Executor reasoning을 전혀 받지 않음 (information isolation).
`permissionMode: bypassPermissions`, `maxTurns: 10`.

pptx 모듈의 경우 Bash로 python-pptx를 직접 실행해 Executor 보고값을 독립 측정.

### Verdict JSON 구조

```json
{
  "verdict": "approved|needs_revision|rejected",
  "score": 0.0,
  "checklist_results": {
    "completeness": true,
    "constraint_compliance": false,
    "content_accuracy": true,
    "design_quality": true
  },
  "constraint_violations": [
    {"constraint": "...", "violation": "...", "severity": "critical|major|minor"}
  ],
  "retry_fix_assessment": [
    {"original_issue": "...", "fixed": true, "regression": false, "notes": "..."}
  ],
  "issues": ["구체적 이슈 + 실측값"],
  "suggestions": ["정확한 좌표/수치 포함 개선안"]
}
```

### 승인 기준

- score ≥ 0.85 AND constraint_violations 없음 → approved
- attempt > 1이고 retry_fixes 비어있으면 → automatic FAIL (-0.3)
- MCP 원칙 위반(prs.save, add_shape 등) 발견 시 → score cap 0.3
