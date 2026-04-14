# Pipeline Rules

## 근거 기반 제안 원칙 (위반 금지)

* 모든 기술적 제안은 공식 문서/블로그/스펙에 근거 필수. 임의 제안 금지.
* 제안 시 참조 URL 또는 문서명 명시.

## Critical (위반 금지)

* ALL module tasks MUST go through the harness pipeline (single-agent execution FORBIDDEN)
* Each agent (Planner, Executor, Reviewer) MUST operate in separate context — NEVER merge into one
* The Reviewer MUST NOT see Executor's internal reasoning — only plan + output
* The agent that produces output NEVER evaluates its own work (No Self-Review)

## Pipeline Flow

1. Evaluate Confidence_Trigger score before choosing pipeline mode
2. Follow: Confidence_Trigger → Guardian → Planner → Executor → Reviewer
3. On review failure, address ALL issues before retrying (max 3-5 per Confidence_Trigger)
4. APPROVED (score >= 0.7): return result. NEEDS_REVISION: retry with feedback.

## Executor v2.0 — Constraint-Aware

* Executor checks ALL constraints (Module SKILL + Sprint Contract) BEFORE each action
* Output includes `constraint_compliance` field (PASS/FAIL per constraint)
* On retry, output includes `retry_fixes` field (root cause + fix per previous issue)
* Constraint priority: Module SKILL > Sprint Contract > acceptance criteria > own judgment
* If action violates constraint → don't execute, report as `blocked_by_constraint`

## Reviewer v2.0 — Constraint Verification

* First step: independently verify `constraint_compliance` (if missing → FAIL)
* On retry: verify `retry_fixes` (if missing → FAIL, if same issue repeated → -0.3)
* Any constraint violation → score capped at 0.3
* Output includes `constraint_violations` and `retry_fix_assessment`

## Execution

* Use structured JSON for all inter-agent communication (schemas/ directory)
* All file writes use Atomic_Write pattern (tmp + mv)
* MCP servers: toggle on before task, off after completion
* Configuration flow: Claude Code → Kiro/Antigravity (one-way, never reverse)

## PPTX Module Specific

* 표지/목차/끝맺음 텍스트 교체 시 서식 보존 필수 (tf.clear() 금지, XML 복제 방식)
* 텍스트가 텍스트박스 너비를 넘으면 자동으로 너비 조정 (auto_fit_textbox_width)
* 끝맺음 슬라이드는 템플릿 그대로 사용 (수정하지 않음)
* 목차 6개 이상 시 자동 페이징 (5개씩, spTree 복제 방식)
* Reviewer는 text_overflow, format_preservation, constraint_compliance 체크리스트 항목을 반드시 검증
* **중제목(subtitle)**: 텍스트 박스 크기 변경 금지, 최대 2줄, 단어 중간 줄바꿈 금지, 초과 시 요약
