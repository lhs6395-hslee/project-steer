# Multi-Agent Harness — Adversarial Review Pipeline

## Overview

이 프로젝트는 하네스 엔지니어링 기반 멀티 에이전트 파이프라인입니다.
각 에이전트(Planner, Executor, Reviewer)는 `claude --print`로 별도 프로세스로 호출되어
컨텍스트가 완전히 분리됩니다.

## Architecture

```
User Request
    │
    ▼
┌─────────┐  claude --print (skills/planner/SKILL.md)
│ Planner │ → 구조화된 실행 계획 생성
└────┬────┘
     │
     ▼
┌──────────┐  claude --print (skills/executor/SKILL.md + modules/{module}/SKILL.md)
│ Executor │ → 계획에 따라 실행, 산출물 생성
└────┬─────┘
     │
     ▼
┌──────────┐  claude --print (skills/reviewer/SKILL.md) — Executor 컨텍스트 차단
│ Reviewer │ → 적대적 검증, 점수 + 판정
└────┬─────┘
     │
     ├─ APPROVED (score >= 0.7) → 결과 반환
     └─ NEEDS_REVISION → 피드백과 함께 Executor 재호출 (최대 3회)
```

## Sub-Agent Execution (Claude Code)

각 에이전트는 별도 프로세스로 호출됩니다:

```bash
# 전체 파이프라인 실행
bash scripts/orchestrate.sh "주간 보고서 프레젠테이션 생성" pptx

# 개별 에이전트 호출 (scripts/agents/call_agent.sh)
bash scripts/agents/call_agent.sh planner input.txt output.json
bash scripts/agents/call_agent.sh executor input.txt output.json pptx
bash scripts/agents/call_agent.sh reviewer input.txt output.json
```

핵심: Reviewer는 Executor의 reasoning을 절대 볼 수 없음 — plan + output만 전달.

## MCP Server Toggle

모든 MCP를 항상 켜둘 필요 없음. 필요할 때만 토글:

```bash
bash scripts/mcp-toggle.sh status           # 전체 상태 확인
bash scripts/mcp-toggle.sh datadog on       # Datadog만 켜기
bash scripts/mcp-toggle.sh pptx off         # PPTX 끄기
```

`.mcp.json` (Claude Code)과 `.kiro/settings/mcp.json` (Kiro)을 동시에 업데이트.

## MCP Servers

| Module | MCP Server | Package |
|--------|-----------|---------|
| pptx | pptx | `uvx --from office-powerpoint-mcp-server pptx_mcp_server` |
| docx | docx | `uvx --from office-word-mcp-server word_mcp_server` |
| trello | trello | `npx mcp-server-trello` |
| wbs | — | Excel 직접 조작 (openpyxl 스크립트) |
| dooray | dooray | `uvx dooray-mcp` |
| datadog | datadog | `npx @winor30/mcp-server-datadog` |
| gdrive | google-workspace | `uvx workspace-mcp` |

Configuration:
- Claude Code: `.mcp.json`
- Kiro: `.kiro/settings/mcp.json`

## Cross-Platform Compatibility

이 프로젝트는 Claude Code를 기본으로 하되, Kiro와 Antigravity에서도 동작합니다.
설정 흐름은 단방향: Claude Code → Kiro/Antigravity (역방향 금지)

| 플랫폼 | 읽는 파일 | 파이프라인 진입점 |
|--------|----------|-----------------|
| Claude Code (Primary) | `CLAUDE.md` + `skills/*/SKILL.md` + `.mcp.json` | `bash scripts/orchestrate.sh` |
| Kiro (Sync) | `AGENTS.md` + `.kiro/steering/` + `.kiro/hooks/` + `.kiro/settings/mcp.json` | Hook: "Run Multi-Agent Pipeline" |
| Antigravity (Sync) | `AGENTS.md` + `.gemini/GEMINI.md` + `.agent/rules/` | Workflow: `/run-pipeline` |

설정 동기화: `bash scripts/mcp-toggle.sh sync` (Claude Code → Kiro 단방향)

## Key Files

```
scripts/
├── orchestrate.sh              # 파이프라인 오케스트레이터
├── mcp-toggle.sh               # MCP 서버 on/off 토글
└── agents/
    └── call_agent.sh           # 범용 서브에이전트 호출기 (claude/gemini 자동 감지)

skills/                         # 에이전트 역할 스킬
├── planner/SKILL.md
├── executor/SKILL.md
├── reviewer/SKILL.md
└── orchestrator/SKILL.md + references/

modules/                        # 도메인별 스킬 (7개 모듈)
├── pptx/SKILL.md
├── docx/SKILL.md
├── wbs/SKILL.md
├── trello/SKILL.md
├── dooray/SKILL.md
├── gdrive/SKILL.md
└── datadog/SKILL.md
```
