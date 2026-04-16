# Multi-Agent Harness — Adversarial Review Pipeline

## 근거 기반 제안 원칙 (CRITICAL — 모든 제안에 적용)

모든 기술적 제안, 아키텍처 결정, 도구 사용 방법은 반드시 **공식 문서, 공식 블로그, 또는 공식 스펙**에 근거해야 한다.
임의로 제안하거나, 추측에 기반한 패턴을 권장하는 것은 금지한다.

- **허용**: 공식 홈페이지, 공식 문서(docs), 공식 블로그, 공식 GitHub README/Wiki, RFC/스펙 문서에 명시된 내용
- **금지**: "~하면 좋을 것 같다", "일반적으로 ~한다", "경험상 ~이다" 등 출처 없는 제안
- **필수**: 제안 시 반드시 참조 문서 URL 또는 문서명을 함께 제시
- **적용 범위**: 하네스 파이프라인, 클라우드(AWS/GCP), MCP, 크로스 플랫폼 sync(Kiro/Antigravity/VS Code), 모듈 작업 전체

## 필수 규칙 (CRITICAL — 모든 작업에 적용)

모듈 작업(pptx, docx, wbs, trello, dooray, gdrive, datadog)은 반드시 하네스 파이프라인으로 실행한다.
싱글 에이전트로 직접 수행하는 것은 금지한다.

**파일 관리 규칙:**
- 원본 파일 외에 백업/수정본을 자동 생성하지 않는다
- 모든 작업 결과는 `.pipeline/` 폴더에만 저장한다
- `results/` 폴더에는 최종 산출물만 유지한다 (중간 버전 금지)
- `.gitignore`에 `*_FIXED*.pptx`, `*_REVIEWED*.pptx`, `*_BACKUP*.pptx` 패턴 등록됨

1. `PROJECT.md`를 읽고 Confidence_Trigger 점수를 산출한다
2. 점수에 따라 파이프라인 모드를 결정한다 (단일/멀티/UltraPlan)
3. 멀티 에이전트 모드: Planner → Executor → Reviewer 순서로 별도 프로세스 실행
4. Reviewer는 Executor의 reasoning을 절대 볼 수 없다
5. 리뷰 실패 시 피드백과 함께 재시도 (Confidence_Trigger 구간에 따라 3~5회)
6. 작업 전 필요한 MCP만 켜고, 완료 후 끈다
7. 모든 파일 쓰기에 Atomic_Write 패턴 적용

## 파이프라인 실행 (v2: Agent Tool Native)

아키텍처 전환 (공식 문서 근거):
- v1: `claude --print` Bash subprocess + `extract_result.py`
- v2: Claude Code native Agent tool + `.claude/agents/` subagent definitions
- 근거: `code.claude.com/docs/en/agent-sdk/subagents.md`, `structured-outputs.md`

```bash
# Step 1: 파이프라인 초기화 (Confidence_Trigger + pipeline_config.json 생성)
bash scripts/orchestrate.sh "<task>" <module>

# Step 2: Claude Code 세션에서 Agent tool로 Planner→Executor→Reviewer 실행
# (orchestrate.sh가 생성한 pipeline_config.json을 읽고 Agent tool 호출)

# 멀티 모듈 (Agent_Team 모드)
bash scripts/orchestrate.sh "<task>" "pptx,dooray,trello"

# MCP 토글
bash scripts/mcp-toggle.sh status
bash scripts/mcp-toggle.sh <server> on|off

# Sync (Claude Code → Kiro/Antigravity)
bash scripts/agents/sync_pipeline.sh --from claude_code --to all
```

### Subagent 정의 파일 (.claude/agents/)

| 파일 | 역할 | 도구 | 모델 |
|------|------|------|------|
| `.claude/agents/planner.md` | Sprint_Contract JSON 생성 | 없음 (tools: []) | sonnet |
| `.claude/agents/executor.md` | MCP 도구로 실행 | MCP + Read/Write/Bash | sonnet |
| `.claude/agents/reviewer.md` | 적대적 검증 (information isolated) | Bash + Read (python-pptx 직접 검증) | sonnet |

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

## 에이전트 정의 (Single Source of Truth)

`.claude/agents/` 가 에이전트 정의의 단일 출처다. `skills/` 는 orchestrator 참조용으로만 유지한다.

| 에이전트 | 정의 파일 |
|---------|----------|
| Planner | `.claude/agents/planner.md` |
| Executor | `.claude/agents/executor.md` |
| Reviewer | `.claude/agents/reviewer.md` |
| Orchestrator 참조 | `skills/orchestrator/SKILL.md` + `skills/orchestrator/references/` |

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

## 에이전트 행동 주의사항 (파이프라인 실수 방지)

과거 세션에서 반복된 실수 패턴 — 이 항목을 위반하면 즉시 사용자에게 보고한다.

1. **세션 시작 시 CLAUDE.md/모듈 SKILL.md 반드시 읽기** — 읽지 않고 작업 시작 금지
2. **MCP 우선 원칙** — 새 콘텐츠(도형/텍스트박스/이미지) 추가는 MCP 도구만 사용. Python으로 직접 생성 금지 (예: `add_shape()`, `add_textbox()`, `add_picture()`, `prs.save()`)
3. **orchestrate.sh = bash 초기화 전용** — Step 1(초기화)만 담당. Step 2(Planner→Executor→Reviewer)는 반드시 Agent tool로 실행
4. **복원 전 버전 확인** — git restore/checkout 전 반드시 커밋 해시와 타임스탬프 확인 후 사용자 승인 받기
5. **단계별 완료 보고** — Plan 완료, 각 Executor 완료, Reviewer 완료 시점에 사용자에게 명시적으로 보고
6. **병렬→순차 전환 금지** — 병렬 실행이 합의된 상태에서 사용자 동의 없이 순차로 변경 금지
7. **MCP 불가 항목 즉시 보고** — MCP로 구현 불가능한 항목 발견 시 즉시 중단하고 대안 제시 (무단 대체 금지)
8. **python-pptx 허용 범위** — `modules/pptx/utils/` 내 지정된 유틸만 사용. 새 shape 생성 용도로 쓰면 위반

## Hooks (Claude Code)

`.claude/settings.json`에 정의:
- `SessionStart`: 파이프라인 리마인더 + sync-to-platforms.sh 실행
- `PreToolUse(Bash)`: guardian.sh로 위험 명령 차단
- `PostToolUse(Edit|Write)`: 설정 변경 시 sync + KAIROS lint
- `Stop`: 파이프라인 준수 여부 prompt 검증

## 크로스 플랫폼

설정 흐름: Claude Code → Kiro/Antigravity (단방향, 역방향 금지)
Sync는 코드 동기화가 아니라 **파이프라인 동작 방식의 동기화**이다.
각 IDE에서 Planner→Executor→Reviewer 역할 분리가 동일하게 동작해야 한다.

| 플랫폼 | 설정 | 진입점 | 역할 분리 |
|--------|------|--------|----------|
| Claude Code (Primary) | `CLAUDE.md` + `.mcp.json` + `.claude/agents/*.md` | `bash scripts/orchestrate.sh` → Agent tool | `.claude/agents/` subagent definitions |
| Kiro (Sync) | `AGENTS.md` + `.kiro/steering/` + `.kiro/settings/mcp.json` | `invokeSubAgent` + Hook | 메인=Planner+Executor, 서브=Reviewer만 분리 |
| Antigravity (Sync) | `AGENTS.md` + `.gemini/GEMINI.md` + `.agent/` | Workflow: `/run-pipeline` | 3단계 별도 컨텍스트 (Step 1/2/3) |
| VS Code (Sync) | `AGENTS.md` + `.vscode/tasks.json` + `.mcp.json` | Task: "Harness: Run Pipeline" | `bash scripts/orchestrate.sh` (터미널) |

동기화: SessionStart Hook → `sync-to-platforms.sh` 자동 실행
수동: `bash scripts/agents/sync_pipeline.sh --from claude_code --to all`
