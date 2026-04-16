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

## 알람 / 백그라운드 현황 (2026-04-16 기준)

**현재 구현된 것**
- 각 Executor step 완료 시: `✅ [Executor 완료] 7p(L02) (42s)` 터미널 출력
- 각 Reviewer step 완료 시: `✅ [Reviewer 완료] 7p(L02)` 터미널 출력
- 단계 완료 출력은 `flush=True`로 즉시 출력됨

**현재 구현되지 않은 것**
- Claude Code 세션으로 돌아오는 알람 (ScheduleWakeup 미사용)
- 백그라운드 실행 — `bash scripts/orchestrate.sh`는 포그라운드 블로킹
  실행 중 Claude Code 세션이 응답하지 않음

**해결 방향 (미구현)**
- Agent tool `run_in_background=True`로 orchestrate 로직 실행
  → Claude Code 세션 즉시 대화 가능 상태 유지
  → 완료 시 자동 알람
