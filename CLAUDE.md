# Multi-Agent Harness — Adversarial Review Pipeline

## 근거 기반 제안 원칙 (CRITICAL — 모든 제안에 적용)

모든 기술적 제안, 아키텍처 결정, 도구 사용 방법은 근거 유형을 **반드시 명시**해야 한다.
추측인지 공식 근거인지 사용자가 구분할 수 없는 답변은 금지한다.

### 답변 시 출처 표기 필수

모든 기술적 답변에 아래 태그 중 하나를 붙인다:

- `[공식]` — 공식 문서/블로그/GitHub README에 명시된 내용 + URL 또는 문서명
- `[외부]` — 논문, 외부 블로그, RFC 등 + URL
- `[추측]` — 공식 문서 없음, 경험적 판단임을 명시

예시:
> `[공식]` code.claude.com/docs/en/sub-agents.md — "Subagents cannot spawn other subagents"
> `[추측]` 공식 문서 없음 — DAG 의존성 처리는 직접 구현이 필요할 것으로 판단

- **금지**: 태그 없이 기술적 사실처럼 서술하는 것 ("~이다", "~해야 한다" 등 출처 불명)
- **적용 범위**: 하네스 파이프라인, 클라우드(AWS/GCP), MCP, 크로스 플랫폼 sync, 모듈 작업 전체

## 필수 규칙 (CRITICAL — 모든 작업에 적용)

모듈 작업(pptx, docx, wbs, trello, dooray, gdrive, datadog)은 반드시 하네스 파이프라인으로 실행한다.
싱글 에이전트로 직접 수행하는 것은 금지한다.

**파일 관리 규칙:**
- 원본 파일 외에 백업/수정본을 자동 생성하지 않는다
- 모든 작업 결과는 `.pipeline/` 폴더에만 저장한다
- `results/` 폴더에는 최종 산출물만 유지한다 (중간 버전 금지)
- `.gitignore`에 `*_FIXED*.pptx`, `*_REVIEWED*.pptx`, `*_BACKUP*.pptx` 패턴 등록됨

## 파이프라인 실행 (v3: Subagents Native)

`[공식]` code.claude.com/docs/en/sub-agents.md — "Run parallel research: spawn multiple subagents to work simultaneously"
`[공식]` code.claude.com/docs/en/sub-agents.md — "mcpServers inline definitions: connected when the subagent starts and disconnected when it finishes"

### Orchestrator 역할 (이 Claude 세션)

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
7. 완료 보고 — 단계별 토큰 합산 테이블 출력:
   | 단계 | input tokens | output tokens | 소계 |
   |------|-------------|---------------|------|
   | Planner | N | N | N |
   | Executor (전체) | N | N | N |
   | Reviewer (전체) | N | N | N |
   | **합계** | **N** | **N** | **N** |

   토큰 수를 가져올 수 없는 경우(Agent tool result에 usage 필드 없음) → 해당 셀에 "N/A" 표기 후 계속 진행
```

### Subagent 호출 방식

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

### recon step 자동 분기 (Orchestrator 판단)

Sprint_Contract 수신 후 executor spawn 전에 아래 기준으로 Create/Modify를 판별한다:

1. `contract.mode == "create"` → Create
2. task 키워드: '생성'/'만들'/'create'/'new'/'새로'/'신규' → Create
3. task 키워드: '수정'/'고쳐'/'변경'/'modify'/'fix'/'update' → Modify
4. steps에 recon step 존재 여부 → Planner 의도 존중 (있으면 Modify)

**Create 모드:** recon step이 있어도 실행하지 않고 건너뜀 (dependency 자동 해제)
**Modify 모드:** recon step 정상 실행 → 완료 후 다음 level steps 병렬 시작

### Subagent 정의 파일 (.claude/agents/)

| 파일 | 역할 | MCP | 모델 |
|------|------|-----|------|
| `planner.md` | Sprint_Contract JSON 생성 | 없음 | sonnet |
| `executor.md` | pptx 실행 | pptx (inline) | sonnet |
| `executor-docx.md` | docx 실행 | docx (inline) | sonnet |
| `executor-dooray.md` | dooray 실행 | dooray (inline) | sonnet |
| `reviewer.md` | 적대적 검증 | Bash + Read | sonnet |

## 스키마

| 파일 | 용도 |
|------|------|
| `schemas/sprint_contract.schema.json` | Planner 출력 |
| `schemas/verdict.schema.json` | Reviewer 출력 |

## 에이전트 행동 주의사항 (파이프라인 실수 방지)

과거 세션에서 반복된 실수 패턴 — 이 항목을 위반하면 즉시 사용자에게 보고한다.

1. **세션 시작 시 CLAUDE.md/모듈 SKILL.md 반드시 읽기** — 읽지 않고 작업 시작 금지
2. **MCP 우선 원칙** — 새 콘텐츠(도형/텍스트박스/이미지) 추가는 MCP 도구만 사용. Python으로 직접 생성 금지 (예: `add_shape()`, `add_textbox()`, `add_picture()`, `prs.save()`)
3. **Executor/Reviewer는 step 정보만 수신** — 전체 Sprint_Contract 전달 금지 (context 낭비 + isolation 위반)
4. **복원 전 버전 확인** — git restore/checkout 전 반드시 커밋 해시와 타임스탬프 확인 후 사용자 승인 받기
5. **단계별 완료 보고 + 토큰 출력** — Planner/각 Executor/각 Reviewer 완료 시 "✅ [역할] STEP N input: N, output: N tokens" 형식으로 즉시 보고. 파이프라인 최종 완료 시 단계별 합산 테이블 출력
6. **병렬→순차 전환 금지** — 병렬 실행이 합의된 상태에서 사용자 동의 없이 순차로 변경 금지
7. **MCP 불가 항목 즉시 보고** — MCP로 구현 불가능한 항목 발견 시 즉시 중단하고 대안 제시 (무단 대체 금지)
8. **python-pptx 허용 범위** — `modules/pptx/utils/` 내 지정된 유틸만 사용. 새 shape 생성 용도로 쓰면 위반

## Hooks (Claude Code)

`.claude/settings.json`에 정의:
- `SessionStart`: 파이프라인 리마인더
- `PreToolUse(Bash)`: `scripts/agents/guardian.sh`로 위험 명령 차단
- `PostToolUse(Edit|Write)`: `scripts/agents/kairos.sh` lint
- `Stop`: 파이프라인 준수 여부 prompt 검증

## 크로스 플랫폼

설정 흐름: Claude Code → Kiro/Antigravity (단방향, 역방향 금지)

수동 동기화: `bash scripts/agents/sync_pipeline.sh --from claude_code --to all`

| 플랫폼 | 설정 | 진입점 |
|--------|------|--------|
| Claude Code (Primary) | `CLAUDE.md` + `.claude/agents/*.md` | Orchestrator = 이 세션 |
| Kiro (Sync) | `AGENTS.md` + `.kiro/steering/` | `invokeSubAgent` |
| Antigravity (Sync) | `AGENTS.md` + `.gemini/GEMINI.md` | Workflow: `/run-pipeline` |
