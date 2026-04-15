# Harness Pipeline — 설계 근거 매핑

> 이 문서는 하네스 파이프라인의 각 설계 결정과 그 근거(공식 문서/연구)를 매핑합니다.
> 보고서 작성 시 이 파일을 참조하세요.

---

## 1. 파이프라인 아키텍처

### 1.1 Planner → Executor → Reviewer 순차 구조

| 항목 | 내용 |
|------|------|
| **구현 위치** | `scripts/orchestrate.sh`, `.claude/agents/` |
| **근거** | Anthropic "Building Effective Agents" — "Evaluator-Optimizer: iterative refinement through feedback loops" |
| **URL** | https://www.anthropic.com/research/building-effective-agents |
| **핵심 인용** | "Orchestrator-Workers: Central LLM delegating to worker instances" |

### 1.2 Planner = opus 모델

| 항목 | 내용 |
|------|------|
| **구현 위치** | `.claude/agents/planner.md` (model: opus), `scripts/agents/call_agent.sh` |
| **근거** | arXiv 2024 — multi-agent pipeline 연구 |
| **핵심 인용** | "A weak planner degrades overall clean task performance more severely than a weak executor" |
| **의미** | Planner가 전체 파이프라인 품질 병목 → 가장 강력한 모델 배치 |

### 1.3 Executor 병렬 실행 (DAG 기반)

| 항목 | 내용 |
|------|------|
| **구현 위치** | `scripts/agents/parallel_executor.py` |
| **근거 1** | Anthropic Claude Code 공식 문서 — subagents parallel execution 패턴 |
| **URL 1** | https://code.claude.com/docs/en/sub-agents |
| **근거 2** | arXiv 2024 VMAO/Maestro — "dependency-aware parallel execution over a DAG" |
| **핵심 인용** | "run style-checker, security-scanner, test-coverage simultaneously, reducing review time from minutes to seconds" |

### 1.4 Reviewer 병렬 실행 (per-step, MoA 앙상블)

| 항목 | 내용 |
|------|------|
| **구현 위치** | `scripts/agents/parallel_reviewer.py` |
| **근거 1** | Claude Code 공식 문서 — parallel subagents 패턴 |
| **URL 1** | https://code.claude.com/docs/en/sub-agents |
| **근거 2** | arxiv.org/abs/2406.04692 — Mixture-of-Agents (Together AI, 2024) |
| **핵심 인용** | "Collective intelligence of multiple LLMs outperforms individual state-of-the-art" |
| **적용** | score² weighted majority voting — 고신뢰도 Reviewer 가중치 강화 |

---

## 2. 정보 차단 (Information Isolation)

### 2.1 Reviewer에 Executor 추론 과정 미전달

| 항목 | 내용 |
|------|------|
| **구현 위치** | `scripts/agents/parallel_reviewer.py` — build_review_input() |
| **근거** | Claude Code 공식 문서 — adversarial review 패턴 |
| **URL** | https://code.claude.com/docs/en/sub-agents |
| **핵심 인용** | "Each subagent runs in its own context window...works independently and returns results" |

### 2.2 Reward Hacking 방어

| 항목 | 내용 |
|------|------|
| **구현 위치** | `.claude/agents/reviewer.md` — "Reward Hacking Prevention" 섹션 |
| **근거** | Anthropic Research "Automated Alignment Researchers" (2026-04-14) |
| **URL** | https://www.anthropic.com/research/automated-alignment-researchers |
| **핵심 인용** | "models attempted to game the evaluation system itself — noticed the most common answer was usually correct and bypassed the teacher entirely" |

---

## 3. 구조화 출력 (Structured Outputs)

### 3.1 --json-schema 플래그

| 항목 | 내용 |
|------|------|
| **구현 위치** | `scripts/agents/call_agent.sh` — 모든 role |
| **근거** | Claude Code CLI 공식 문서 |
| **URL** | https://code.claude.com/docs/en/cli-reference |
| **핵심 인용** | "Get validated JSON output matching a JSON Schema after agent completes its workflow" |

### 3.2 error_max_structured_output_retries 처리

| 항목 | 내용 |
|------|------|
| **구현 위치** | `scripts/agents/call_agent.sh` — extract_structured_output() |
| **근거** | Claude Code Agent SDK 공식 문서 |
| **URL** | https://code.claude.com/docs/en/agent-sdk/structured-outputs |
| **핵심 인용** | "subtype: error_max_structured_output_retries — agent couldn't produce valid output after multiple attempts" |

---

## 4. 속도 개선

### 4.1 --exclude-dynamic-system-prompt-sections

| 항목 | 내용 |
|------|------|
| **구현 위치** | `scripts/agents/call_agent.sh` — planner, reviewer |
| **근거** | Claude Code CLI 공식 문서 (신규 플래그) |
| **URL** | https://code.claude.com/docs/en/cli-reference |
| **핵심 인용** | "Improves prompt-cache reuse across different users and machines running the same task" |

### 4.2 --effort 플래그

| 항목 | 내용 |
|------|------|
| **구현 위치** | `scripts/agents/call_agent.sh`, `.claude/agents/*.md` |
| **근거** | Claude Code 모델 설정 공식 문서 |
| **URL** | https://code.claude.com/docs/en/model-config |
| **핵심 인용** | "Effort levels control adaptive reasoning, which dynamically allocates thinking based on task complexity" |

### 4.3 --fallback-model

| 항목 | 내용 |
|------|------|
| **구현 위치** | `scripts/agents/call_agent.sh` — executor |
| **근거** | Claude Code CLI 공식 문서 (신규 플래그) |
| **URL** | https://code.claude.com/docs/en/cli-reference |
| **핵심 인용** | "Enable automatic fallback to specified model when default model is overloaded" |

---

## 5. 보안

### 5.1 Indirect Prompt Injection 방어 (Guardian)

| 항목 | 내용 |
|------|------|
| **구현 위치** | `scripts/agents/guardian.sh` |
| **근거** | arXiv 2024 ClawGuard/CoopGuard 프레임워크 |
| **핵심 인용** | "user-confirmed rule set at every tool-call boundary to prevent malicious tool calls" |
| **적용** | MCP tool input의 path/file_path를 allow-list 방식으로 검증 |

### 5.2 Plan Transparency (Plan Mode)

| 항목 | 내용 |
|------|------|
| **구현 위치** | `scripts/orchestrate.sh` — PLAN_REVIEW=1 |
| **근거** | Anthropic "Trustworthy Agents" (2026-04-09) |
| **URL** | https://www.anthropic.com/research/trustworthy-agents |
| **핵심 인용** | "Plan Mode shifts oversight from the individual step to the overall strategy — users review and authorize the complete plan before execution" |

---

## 6. 서브에이전트 설정

### 6.1 isolation: worktree (Executor)

| 항목 | 내용 |
|------|------|
| **구현 위치** | `.claude/agents/executor.md` |
| **근거** | Claude Code 서브에이전트 공식 문서 |
| **URL** | https://code.claude.com/docs/en/sub-agents#supported-frontmatter-fields |
| **핵심 인용** | "Set to worktree to run the subagent in a temporary git worktree, giving it an isolated copy of the repository" |

### 6.2 memory: project (Reviewer)

| 항목 | 내용 |
|------|------|
| **구현 위치** | `.claude/agents/reviewer.md` |
| **근거** | Claude Code 서브에이전트 공식 문서 |
| **URL** | https://code.claude.com/docs/en/sub-agents#supported-frontmatter-fields |
| **핵심 인용** | "Persistent memory scope: project — Enables cross-session learning" |

---

## 7. 버그 수정 (코드 품질)

| # | 이슈 | 수정 위치 | 분류 |
|---|------|---------|------|
| #1 | Guardian JSON 주입 취약점 | orchestrate.sh | 보안 |
| #2 | Executor 실패 시 계속 진행 | orchestrate.sh | 버그 |
| #3 | aggregated output 파일 존재 확인 (-f → -s) | orchestrate.sh | 버그 |
| #4 | step 파일 파싱 IndexError | parallel_executor.py | 버그 |
| #8 | constraint_violations required 아님 | verdict.schema.json | 스키마 |
| #9 | executor_output에 plan 필드 불일치 | executor_output.schema.json | 스키마 |
| #10 | timeout 하드코딩 vs env var 불일치 | parallel_executor.py | 버그 |
| #11 | JSON 3회 중복 파싱 | orchestrate.sh | 효율성 |
| #12 | parallel_executor.sh 데드코드 | scripts/agents/ | 정리 |
| #13 | thread pool 하드캡 4 | parallel_reviewer.py | 효율성 |
| #17 | DAG 사이클 검증 없음 | parallel_executor.py | 버그 |
| #18 | 오류 시 verdict 파일 미생성 | parallel_reviewer.py | 버그 |
| #21 | executor output 포맷 불일치 | executor_output.schema.json | 스키마 |
| #23 | risks 필드 타입 불일치 | sprint_contract.schema.json | 스키마 |
| #27 | MCP_CONFIG 하드코딩 | call_agent.sh | 일관성 |
| #28 | block-list → allow-list 보안 | guardian.sh | 보안 |
| #30 | verdict 승인 threshold 불일치 (0.7 vs 0.9) | orchestrate.sh | 버그 |

---

## 참고 문헌

1. Anthropic — Building Effective Agents (2024): https://www.anthropic.com/research/building-effective-agents
2. Anthropic — Trustworthy Agents (2026-04-09): https://www.anthropic.com/research/trustworthy-agents
3. Anthropic — Measuring Agent Autonomy (2026-02-18): https://www.anthropic.com/research/measuring-agent-autonomy
4. Anthropic — Automated Alignment Researchers (2026-04-14): https://www.anthropic.com/research/automated-alignment-researchers
5. Together AI — Mixture-of-Agents (2024): https://arxiv.org/abs/2406.04692
6. Claude Code CLI Reference: https://code.claude.com/docs/en/cli-reference
7. Claude Code Subagents: https://code.claude.com/docs/en/sub-agents
8. Claude Code Structured Outputs: https://code.claude.com/docs/en/agent-sdk/structured-outputs
9. Claude Code Model Config: https://code.claude.com/docs/en/model-config
10. arXiv 2024 — ClawGuard/CoopGuard (IPI defense): adversarial robustness multi-agent systems
