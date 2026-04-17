# 파이프라인 실행 (v3: Subagents Native)

`[공식]` code.claude.com/docs/en/sub-agents.md — "Run parallel research: spawn multiple subagents to work simultaneously"
`[공식]` code.claude.com/docs/en/sub-agents.md — "mcpServers inline definitions: connected when the subagent starts and disconnected when it finishes"

## Orchestrator 역할 (이 Claude 세션)

모듈 작업 요청이 오면 **반드시** 아래 순서로 subagents를 직접 실행한다:

```
1. @planner → Sprint_Contract JSON 생성 (순차 1회)
   → 완료 시 보고: "✅ [Planner] input: N, output: N tokens"
2. Sprint_Contract의 dependency level 분석
3. level 0 steps → executor subagents 동시 spawn
   → 각 완료 시 보고: "✅ [Executor] STEP N input: N, output: N tokens"
4. level 0 완료 후 → level 1 steps → executor subagents 동시 spawn
   → 각 완료 시 보고: "✅ [Executor] STEP N input: N, output: N tokens"
5. 전체 executor 완료 → reviewer subagents 동시 spawn
   → 각 완료 시 보고: "✅ [Reviewer] STEP N input: N, output: N tokens"
6. 실패 step만 재시도 (approved step 스킵, max 5회)
7. 완료 보고 — 단계별 토큰 합산 + 비용 환산 테이블 출력:
   | 단계 | input tokens | output tokens | 소계 tokens | 비용 (USD) |
   |------|-------------|---------------|-------------|-----------|
   | Planner | N | N | N | $N.NNNN |
   | Executor (전체) | N | N | N | $N.NNNN |
   | Reviewer (전체) | N | N | N | $N.NNNN |
   | **합계** | **N** | **N** | **N** | **$N.NNNN** |

   **비용 환산 공식 (Vertex AI On-demand 기준, `[공식]` cloud.google.com/vertex-ai/generative-ai/pricing):**
   - Claude Sonnet 4.6: input $3.00/1M tokens, output $15.00/1M tokens
   - Claude Haiku 4.5: input $1.00/1M tokens, output $5.00/1M tokens
   - Claude Opus 4.6: input $5.00/1M tokens, output $25.00/1M tokens
   - 단계별 비용 = (input_tokens / 1,000,000 × input_price) + (output_tokens / 1,000,000 × output_price)
   - 모델 혼용 시 각 subagent 모델에 맞는 가격 적용 (기본: Sonnet 4.6)

   **토큰 집계 방법 (Orchestrator 직접 계산):**
   - Agent tool result 하단의 `<usage>total_tokens: N / tool_uses: N / duration_ms: N</usage>` 블록에서 값 추출
   - `total_tokens`가 없으면 `input: N, output: N tokens` 보고 문자열에서 파싱
   - 토큰 수를 가져올 수 없는 경우 → 해당 셀에 "N/A" 표기 후 계속 진행
   - **usage 블록의 total_tokens는 input+output 합산값** → input/output 분리가 불가한 경우 total만 표시하고 비용은 output 비율 30% 가정으로 추정
   - 파이프라인 전체 완료 시 합계 비용을 **USD** 및 **KRW(환율 1,380원 기준)** 모두 표시
```

## Subagent 호출 방식

`[공식]` code.claude.com/docs/en/sub-agents.md — "@-mention guarantees the subagent runs"

```
# Planner (순차)
@planner "Task: ..., Module: ..., 스키마: schemas/sprint_contract.schema.json"

# Executor (병렬 — 동시에 여러 개)
@executor "STEP 2: Slide 3 (L02) 생성 — /tmp/slide_3.pptx, acceptance_criteria: [...], constraints: [...]"
@executor "STEP 3: Slide 5 (L03) 생성 — /tmp/slide_5.pptx, acceptance_criteria: [...], constraints: [...]"

# Reviewer (병렬 — 동시에 여러 개)
@reviewer "STEP 2 검증: action=..., acceptance_criteria=..., step_output=<파일 경로>"
@reviewer "STEP 3 검증: action=..., acceptance_criteria=..., step_output=<파일 경로>"
```

- Executor/Reviewer는 각자의 step 정보만 받는다 (전체 Sprint_Contract 전달 금지)
- Reviewer는 Executor의 reasoning을 볼 수 없다 (information isolation)
- MCP는 각 executor subagent의 mcpServers에서 자동 연결/해제

## recon step 자동 분기 (Orchestrator 판단)

Sprint_Contract 수신 후 executor spawn 전에 아래 기준으로 Create/Modify를 판별한다:

1. `contract.mode == "create"` → Create
2. task 키워드: '생성'/'만들'/'create'/'new'/'새로'/'신규' → Create
3. task 키워드: '수정'/'고쳐'/'변경'/'modify'/'fix'/'update' → Modify
4. steps에 recon step 존재 여부 → Planner 의도 존중 (있으면 Modify)

**Create 모드:** recon step이 있어도 실행하지 않고 건너뜀 (dependency 자동 해제)
**Modify 모드:** recon step 정상 실행 → 완료 후 다음 level steps 병렬 시작

## Subagent 정의 파일 (.claude/agents/)

| 파일 | 역할 | MCP | 모델 |
|------|------|-----|------|
| `planner.md` | Sprint_Contract JSON 생성 | 없음 | opus |
| `executor.md` | pptx 실행 | pptx (inline) | sonnet |
| `executor-docx.md` | docx 실행 | docx (inline) | sonnet |
| `executor-dooray.md` | dooray 실행 | dooray (inline) | sonnet |
| `reviewer.md` | 적대적 검증 | Bash + Read | sonnet |

## 스키마

| 파일 | 용도 |
|------|------|
| `schemas/sprint_contract.schema.json` | Planner 출력 |
| `schemas/verdict.schema.json` | Reviewer 출력 |
