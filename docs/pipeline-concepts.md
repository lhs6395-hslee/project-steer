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

## 알람 / 백그라운드 (2026-04-16 구현)

### 왜 Agent tool run_in_background인가

`bash scripts/orchestrate.sh`는 포그라운드 블로킹이다.
실행 중 Claude Code 세션이 응답하지 않아 사용자가 대화할 수 없다.

Agent tool `run_in_background=True`를 사용하면:
- orchestrate.sh가 별도 Agent로 실행됨
- Claude Code 세션은 즉시 대화 가능 상태로 복귀
- Agent 완료 시 세션에 자동 알람이 옴 (완료 결과 보고 가능)

### 실행 방법

```python
# CLAUDE.md 기준 — 모듈 작업 요청 시 반드시 이 방식 사용
Agent(
    description="파이프라인: <task 요약>",
    prompt="bash scripts/orchestrate.sh '<task>' <module>",
    run_in_background=True
)
```

### 단계별 알람 현황

- 각 Executor step 완료: `✅ [Executor 완료] 7p(L02) (42s)` — Agent 로그에 출력
- 각 Reviewer step 완료: `✅ [Reviewer 완료] 7p(L02)` — Agent 로그에 출력
- 전체 파이프라인 완료: Agent 종료 → Claude Code 세션 자동 알람
- 실패/에스컬레이션: 완료 알람 수신 후 결과 파일에서 확인

## recon step — Create/Modify 자동 분기 (2026-04-16 구현)

### 왜 로직으로 구현했는가

Planner에게 "Create면 recon 넣지 마"를 지시하면:
- Planner context 소비 증가 (지시문 토큰)
- Planner 실수 가능성 (Create인데 recon 넣는 경우)
- 매번 Planner가 판단해야 하므로 불안정

코드(`parallel_executor.py`)가 자동으로 판별하면:
- Planner는 내용 설계에만 집중
- 실행 레이어에서 안전망 역할
- 실행 로그에 명시적으로 표시됨

### 판별 로직 (우선순위 순)

1. `contract['mode']` 필드가 `'create'` → Create
2. `contract['task']` 키워드: '생성'/'create'/'new' → Create, '수정'/'fix' → Modify
3. steps에 recon step 존재 여부 → Planner 의도 존중 (있으면 Modify)

### 동작

- Create 모드: recon step을 실행하지 않고 `completed_outputs`에 추가 (dependency 해제)
- Modify 모드: recon step 정상 실행 → step1 완료 후 step2~N 병렬 시작
