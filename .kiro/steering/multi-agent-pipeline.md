---
inclusion: auto
---

# Multi-Agent Adversarial Review Pipeline

이 프로젝트는 하네스 엔지니어링 기반 멀티 에이전트 파이프라인이다.
모든 작업은 반드시 Planner → Executor → Reviewer 순서로 수행한다.

## 필수 실행 규칙 (CRITICAL)

모듈 작업(pptx, docx, wbs, trello, dooray, gdrive, datadog)은 반드시 하네스 파이프라인으로 실행한다.
싱글 에이전트로 직접 수행하는 것은 금지한다.

### Kiro 실행 모델 (속도 최적화)

Kiro에서는 `invokeSubAgent`의 순차 실행 한계로 인해 아래 최적화 모델을 적용한다:
- **메인 에이전트**: Planner + Executor 역할 수행 (MCP I/O 직접 처리)
- **서브에이전트**: Reviewer만 분리 (확증편향 방지의 핵심)

이유:
- `invokeSubAgent`는 순차 실행이라 3번 호출 시 3배 느림
- 서브에이전트는 MCP 도구 직접 접근 불가
- Reviewer만 분리하면 "자기가 만든 걸 자기가 검증" 문제를 방지하면서 속도 확보

### 실행 흐름

1. PROJECT.md를 읽고 Confidence_Trigger 점수를 산출한다
2. 점수에 따라 파이프라인 모드를 결정한다
3. **메인이 직접** Planner 역할 수행 → 실행 계획(JSON) 생성 → `results/{module}/plan-*.json` 저장
4. **메인이 직접** Executor 역할 수행 → 계획대로 실행 → 산출물 생성
5. **invokeSubAgent로** Reviewer 호출 → 적대적 검증 → `results/{module}/review-*.json` 저장
6. APPROVED (score >= 0.7): 결과 반환 / NEEDS_REVISION: 메인이 수정 후 Reviewer 재호출

### Step 1~2: Planner + Executor (메인 직접 수행)

메인 에이전트가 `skills/planner/SKILL.md`와 `skills/executor/SKILL.md`를 참조하여:
- 실행 계획 생성 (acceptance_criteria, constraints, risks 포함)
- 계획대로 실행 (MCP 도구 직접 사용)
- 결과를 `results/` 하위에 저장

### Step 3: Reviewer (서브에이전트 호출)

```
invokeSubAgent:
  name: general-task-execution
  prompt: |
    당신은 Reviewer 에이전트입니다.
    skills/reviewer/SKILL.md의 지침에 따라 적대적으로 검증하세요.
    계획: {Planner 출력 — results/{module}/plan-*.json}
    실행 결과: {Executor 출력 파일 경로}
    Executor의 의도나 reasoning은 제공되지 않습니다.
    체크리스트 평가, 점수(0.0~1.0), 판정(approved/needs_revision/rejected)을 출력하세요.
  contextFiles: [skills/reviewer/SKILL.md, skills/orchestrator/references/module-checklists.md]
```

### Step 4: 재시도 또는 완료

- APPROVED (score >= 0.7): 결과 반환
- NEEDS_REVISION: Reviewer의 이슈를 메인이 직접 수정 후 Reviewer 재호출 (최대 3~5회)
- 최대 재시도 소진: 전체 이력과 함께 사용자에게 에스컬레이션

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
Sync는 코드 동기화가 아니라 **파이프라인 동작 방식의 동기화**이다.

## PPTX 모듈 특화 규칙

- 표지/목차/끝맺음 텍스트 교체 시 서식 보존 필수 (tf.clear() 금지, XML 복제 방식: `replace_text_preserve_format` / `replace_multiline_preserve_format`)
- 텍스트가 텍스트박스 너비를 넘으면 자동으로 너비 조정 (`auto_fit_textbox_width`)
- 표지 제목: 50pt 유지, 좌우 중앙 배치, 높이 2.8" (3줄 수용), 수직 중앙
- 끝맺음 슬라이드는 템플릿 그대로 사용 (수정하지 않음)
- 목차 6개 이상 시 자동 페이징 (5개씩, spTree 복제 방식)
- Reviewer는 text_overflow, format_preservation 체크리스트 항목을 반드시 검증
