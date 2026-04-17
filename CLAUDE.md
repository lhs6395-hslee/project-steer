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

**파이프라인 실행 규칙:**
- **Executor/Reviewer는 step 정보만 수신** — 전체 Sprint_Contract 전달 금지 (isolation 위반)
- **병렬→순차 전환 금지** — 병렬 실행 합의 후 사용자 동의 없이 순차 변경 금지
- **MCP 불가 항목 즉시 보고** — 무단 대체 금지

**파일 관리 규칙:**
- 원본 파일 외에 백업/수정본을 자동 생성하지 않는다
- 모든 작업 결과는 `.pipeline/` 폴더에만 저장한다
- `results/` 폴더에는 최종 산출물만 유지한다 (중간 버전 금지)
- `.gitignore`에 `*_FIXED*.pptx`, `*_REVIEWED*.pptx`, `*_BACKUP*.pptx` 패턴 등록됨

## 파이프라인 실행

@.claude/docs/pipeline-orchestration.md

## Hooks / 크로스플랫폼

**Hooks** — `.claude/settings.json`에 정의:
- `SessionStart`: 파이프라인 리마인더
- `PreToolUse(Bash)`: `scripts/agents/guardian.sh`로 위험 명령 차단
- `PostToolUse(Edit|Write)`: `scripts/agents/kairos.sh` lint
- `Stop`: 파이프라인 준수 여부 prompt 검증

**크로스플랫폼** — 설정 흐름: Claude Code → Kiro/Antigravity (단방향, 역방향 금지)
수동 동기화: `/sync-platforms` skill 또는 `bash scripts/agents/sync_pipeline.sh --from claude_code --to all`
