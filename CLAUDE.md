# Multi-Agent Harness — Adversarial Review Pipeline

## 필수 규칙 (CRITICAL — 모든 작업에 적용)

모듈 작업(pptx, docx, wbs, trello, dooray, gdrive, datadog)은 반드시 하네스 파이프라인으로 실행한다.
싱글 에이전트로 직접 수행하는 것은 금지한다.

1. `PROJECT.md`를 읽고 Confidence_Trigger 점수를 산출한다
2. 점수에 따라 파이프라인 모드를 결정한다 (단일/멀티/UltraPlan)
3. 멀티 에이전트 모드: Planner → Executor → Reviewer 순서로 별도 프로세스 실행
4. Reviewer는 Executor의 reasoning을 절대 볼 수 없다
5. 리뷰 실패 시 피드백과 함께 재시도 (Confidence_Trigger 구간에 따라 3~5회)
6. 작업 전 필요한 MCP만 켜고, 완료 후 끈다
7. 모든 파일 쓰기에 Atomic_Write 패턴 적용

## 파이프라인 실행

```bash
# 전체 파이프라인 (Confidence_Trigger → Guardian → Planner → Executor → Reviewer)
bash scripts/orchestrate.sh "<task>" <module>

# 멀티 모듈 (Agent_Team 모드)
bash scripts/orchestrate.sh "<task>" "pptx,dooray,trello"

# MCP 토글
bash scripts/mcp-toggle.sh status
bash scripts/mcp-toggle.sh <server> on|off

# Sync (Claude Code → Kiro/Antigravity)
bash scripts/agents/sync_pipeline.sh --from claude_code --to all
```

## Confidence_Trigger 구간

| 점수 | 모드 | 재시도 | UltraPlan |
|------|------|--------|-----------|
| ≥0.85 | 단일 에이전트 | N/A | 비활성 |
| 0.70-0.84 | 멀티 (축소) | 3회 | 비활성 |
| 0.50-0.69 | 멀티 (전체) | 5회 | 비활성 |
| <0.50 | 멀티 + UltraPlan | 5회 | 활성 |

## 에이전트 스크립트

| 스크립트 | 역할 | 요구사항 |
|---------|------|---------|
| `scripts/orchestrate.sh` | 파이프라인 오케스트레이터 | R1 |
| `scripts/agents/call_agent.sh` | 서브에이전트 호출 (claude/gemini 자동 감지) | R7, R10 |
| `scripts/agents/confidence_trigger.sh` | 4차원 위험도 평가 | R13 |
| `scripts/agents/guardian.sh` | Pattern_Matcher 위험 명령 차단 | R5 |
| `scripts/agents/ide_adapter.sh` | 런타임 IDE 감지 + 경로 매핑 | R15 |
| `scripts/agents/kairos.sh` | 경량 사전 감시 (lint-level) | R19 |
| `scripts/agents/auto_dream.sh` | 메모리 파일 자동 정리 | R18 |
| `scripts/agents/ultraplan.sh` | 계층적 태스크 분해 | R20 |
| `scripts/agents/token_tracker.sh` | 비용/토큰 관리 | R14 |
| `scripts/agents/harness_subtraction.sh` | 하네스 최적화 분석 | R23 |
| `scripts/agents/agent_team.sh` | 멀티 모듈 팀 협업 | R22 |
| `scripts/agents/git_worktree.sh` | 병렬 실행 worktree 관리 | R17 |
| `scripts/agents/sdd_integrator.sh` | Spec-Driven Development 통합 | R21 |
| `scripts/agents/sync_pipeline.sh` | IDE 간 설정 동기화 | R16 |
| `scripts/mcp-toggle.sh` | MCP 서버 on/off 토글 | — |

## 스키마

| 파일 | 용도 |
|------|------|
| `schemas/sprint_contract.schema.json` | Planner 출력 (R11) |
| `schemas/verdict.schema.json` | Reviewer 출력 (R12) |
| `schemas/handoff_file.schema.json` | 에이전트 간 통신 (R6) |

## 에이전트 스킬

| 에이전트 | 스킬 |
|---------|------|
| Planner | `skills/planner/SKILL.md` |
| Executor | `skills/executor/SKILL.md` |
| Reviewer | `skills/reviewer/SKILL.md` |
| Orchestrator | `skills/orchestrator/SKILL.md` |

## 모듈 + MCP

| 모듈 | MCP 서버 | 패키지 |
|------|---------|--------|
| pptx | pptx | `uvx --from office-powerpoint-mcp-server ppt_mcp_server` |
| docx | docx | `uvx --from office-word-mcp-server word_mcp_server` |
| trello | trello | `npx mcp-server-trello` |
| wbs | — | Excel 직접 조작 |
| dooray | dooray | `uvx dooray-mcp` |
| datadog | datadog | `npx @winor30/mcp-server-datadog` |
| gdrive | google-workspace | `uvx workspace-mcp` |

## Hooks (Claude Code)

`.claude/settings.json`에 정의:
- `SessionStart`: 파이프라인 리마인더 + sync-to-platforms.sh 실행
- `PreToolUse(Bash)`: guardian.sh로 위험 명령 차단
- `PostToolUse(Edit|Write)`: 설정 변경 시 sync + KAIROS lint
- `Stop`: 파이프라인 준수 여부 prompt 검증

## 크로스 플랫폼

설정 흐름: Claude Code → Kiro/Antigravity (단방향, 역방향 금지)

| 플랫폼 | 설정 | 진입점 |
|--------|------|--------|
| Claude Code (Primary) | `CLAUDE.md` + `.mcp.json` + `.claude/settings.json` | `bash scripts/orchestrate.sh` |
| Kiro (Sync) | `AGENTS.md` + `.kiro/steering/` + `.kiro/settings/mcp.json` | `invokeSubAgent` + Hook |
| Antigravity (Sync) | `AGENTS.md` + `.gemini/GEMINI.md` + `.agent/` | Workflow: `/run-pipeline` |
| VS Code (Sync) | `AGENTS.md` + `.vscode/tasks.json` + `.mcp.json` | Task: "Harness: Run Pipeline" |

동기화: SessionStart Hook → `sync-to-platforms.sh` 자동 실행
수동: `bash scripts/agents/sync_pipeline.sh --from claude_code --to all`
