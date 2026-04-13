# Pipeline Rules

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
* Reviewer는 text_overflow, format_preservation 체크리스트 항목을 반드시 검증
