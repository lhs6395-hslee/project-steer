# 프로젝트 에러 및 의사결정 기록

> 발생한 에러, 잘못된 판단, 올바른 해결 방향을 기록합니다.
> 보고서 작성 및 팀 공유용.

---

## 2026-04-15

### E01 — Vertex AI 모델 ID 형식 오류

**에러**: `API Error: 400 The provided model identifier is invalid`

**잘못된 판단**: Vertex AI도 Bedrock과 동일한 `us.anthropic.claude-*-v1:0` 형식을 사용한다고 추측

**실제 원인**: Vertex AI와 Bedrock은 모델 ID 형식이 다름
- Bedrock: `us.anthropic.claude-opus-4-6-v1`, `us.anthropic.claude-sonnet-4-5-20250929-v1:0`
- Vertex AI: `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5@20251001`

**공식 문서**: `code.claude.com/docs/en/google-vertex-ai` — "Pin model versions" 섹션
```bash
export ANTHROPIC_DEFAULT_OPUS_MODEL='claude-opus-4-6'
export ANTHROPIC_DEFAULT_SONNET_MODEL='claude-sonnet-4-6'
export ANTHROPIC_DEFAULT_HAIKU_MODEL='claude-haiku-4-5@20251001'
```

**교훈**: 추측으로 모델 ID 변경 금지. 반드시 공식 문서의 provider별 섹션 확인 후 변경.

---

### E02 — --effort high + --json-schema 충돌 (thinking mode)

**에러**: `API Error: 400 messages.1.content.0.type: Expected 'thinking' or 'redacted_thinking', but found 'tool_use'. When 'thinking' is enabled, a final 'assistant' message must start with a thinking block`

**원인**: `--effort high`가 Opus에서 adaptive thinking(extended thinking) 모드를 활성화하는데, thinking 모드에서는 assistant 응답이 반드시 thinking block으로 시작해야 함. `--json-schema`가 구조화 출력을 강제하는 과정에서 tool_use가 먼저 오는 경우 충돌 발생.

**해결**: `--effort medium`으로 낮춰 thinking 모드 비활성화

**공식 문서**: `code.claude.com/docs/en/model-config#adjust-effort-level`
> "higher effort provides deeper reasoning for complex problems... can cause the model to overthink routine work"

**교훈**: `--json-schema`와 함께 사용할 때는 `--effort medium` 이하 사용. high/max는 thinking을 활성화해 structured output 파이프라인과 충돌 가능.

---

### E03 — --bare 모드에서 settings.json env 미적용

**에러**: Planner가 opus alias 사용 시 응답 없음 (무한 대기)

**원인**: `--bare` 플래그는 settings.json을 로드하지 않음. 따라서 settings.json의 `ANTHROPIC_DEFAULT_OPUS_MODEL` env가 subprocess에 전달되지 않아 alias가 resolve되지 않음.

**해결**: `call_agent.sh`에서 `~/.claude/settings.json`의 env 블록을 직접 읽어 `export` 처리

**공식 문서**: `code.claude.com/docs/en/cli-reference.md#--bare`
> "Minimal mode: skip auto-discovery of hooks, skills, plugins, MCP servers, auto memory, and CLAUDE.md"
> (settings.json도 스킵됨)

**교훈**: `--bare` 모드 subprocess에서 settings.json 의존 env는 명시적으로 export 필요.

---

### E04 — parallel_executor.py 들여쓰기 오류 (audit 수정 regression)

**에러**: `IndentationError: unexpected indent` (line 173)

**원인**: aggregate_results 함수의 regex 파일 매칭 수정(#4 audit fix) 시 들여쓰기가 잘못 적용됨. `for` 루프 내부 코드가 `if not m: continue` 블록에 잘못 들여쓰여짐.

**해결**: 들여쓰기 수정 (for 루프 레벨로 복원)

**교훈**: 들여쓰기 수정 시 전후 context를 충분히 확인. 특히 `if not m: continue` 뒤의 코드 레벨에 주의.

---

### D01 — Planner 모델 선택: sonnet → opus

**결정**: Planner를 sonnet에서 opus로 변경

**근거**: arXiv 2024 멀티에이전트 파이프라인 연구
> "A weak planner degrades overall clean task performance more severely than a weak executor"

**의미**: Planner의 Sprint_Contract 품질이 전체 파이프라인 품질을 결정. Executor나 Reviewer보다 Planner에 더 강력한 모델 배치.

**트레이드오프**: opus는 sonnet 대비 느리고 비쌈. 단, Planner는 1회만 실행되므로 병렬화 이득이 없는 유일한 단계 → 품질 투자 가치 있음.

---

### D02 — Reviewer 병렬화 (MoA 앙상블)

**결정**: Reviewer를 step별 병렬 실행 + weighted majority voting 도입

**근거**: arxiv.org/abs/2406.04692 (Mixture-of-Agents, Together AI 2024)
> "Collective intelligence of multiple LLMs outperforms individual state-of-the-art"

**기존 방식**: 단일 Reviewer가 전체 executor output을 순차 검토
**개선 방식**: step별 독립 Reviewer를 병렬 실행, score² weighted majority로 집계

**트레이드오프**: Reviewer 비용 N배 증가. 단, wall-clock time은 감소(병렬화).

---

### D03 — isolation: worktree (Executor subagent)

**결정**: Executor subagent에 `isolation: worktree` 설정

**근거**: Claude Code 공식 문서 `code.claude.com/docs/en/sub-agents`
> "run the subagent in a temporary git worktree, giving it an isolated copy of the repository"

**이유**: 병렬 Executor step들이 동일 파일을 동시 수정 시 충돌 방지. 각 step이 독립 worktree에서 작업.

---

### D04 — Guardian allow-list 방식 전환

**결정**: block-list에서 allow-list 방식으로 전환

**근거**: arXiv 2024 ClawGuard/CoopGuard
> "user-confirmed rule set at every tool-call boundary"

**이유**: block-list는 열거하지 않은 경로로 우회 가능. allow-list는 허용된 경로 외 모두 차단.

**허용 경로**: 프로젝트 디렉토리, `/tmp`, `~/.claude/projects|agent-memory`

---

### D05 — verdict threshold 0.7 → 0.85

**결정**: Reviewer 승인 threshold를 0.7에서 0.85로 상향

**이유**: reviewer.md에 "0.9-1.0 = High quality, approved"라고 명시되어 있는데 orchestrate.sh가 0.7을 기준으로 approved 처리 → 불일치. 일관성을 위해 0.85로 조정.

**트레이드오프**: threshold 높을수록 retry 횟수 증가 가능. 단, 품질 기준 일관성이 더 중요.
