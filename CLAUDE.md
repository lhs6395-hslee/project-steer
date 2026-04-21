# Multi-Agent Harness — Adversarial Review Pipeline

## 문서 구조 (CRITICAL — LLM 필독)

이 프로젝트의 문서는 두 계층으로 나뉜다.

| 위치 | 역할 | 포함 내용 |
|------|------|---------|
| **루트** (`CLAUDE.md`, `PROJECT.md`, `AGENTS.md`) | 멀티 모듈 오케스트레이션 | 파이프라인 원칙, 에이전트 역할, 크로스 플랫폼, 모듈 목록 |
| **`modules/<module>/`** | 모듈별 실행 규칙 | SKILL.md(실행 방법), MISTAKES.md(재발 방지), references/(스펙), utils/(유틸) |

**규칙**: 모듈 작업 시 반드시 해당 `modules/<module>/SKILL.md`를 읽어야 한다. 직접실행 기준, MCP 사용법, 검증 절차 등 모듈별 세부 규칙은 루트가 아닌 모듈 디렉토리에 있다.

현재 활성 모듈:
- `modules/pptx/` — SKILL.md, MISTAKES.md, references/layout-spec.md, utils/

---

## 근거 기반 제안 원칙 (CRITICAL — 모든 제안에 적용)

모든 기술적 제안, 아키텍처 결정, 도구 사용 방법은 근거 유형을 **반드시 명시**해야 한다.

- `[공식]` — 공식 문서/블로그/GitHub README + URL 또는 문서명
- `[외부]` — 논문, 외부 블로그, RFC 등 + URL
- `[추측]` — 공식 문서 없음, 경험적 판단임을 명시

**금지**: 태그 없이 기술적 사실처럼 서술 ("~이다", "~해야 한다" 등 출처 불명)
**적용 범위**: 파이프라인, 클라우드(AWS/GCP), MCP, 크로스 플랫폼 sync, 모듈 작업 전체

---

## 필수 규칙 (CRITICAL — 모든 작업에 적용)

### 파이프라인 실행 판단 기준

**복잡한 작업 → 파이프라인 필수:**
- 다중 산출물 생성 (3개 이상)
- 데이터 검증이 필요한 작업
- 외부 API 연동 (dooray, google_workspace, datadog)

**단순 작업 → 직접 실행 허용:**
- 텍스트/색상/폰트 수정
- 파일 순서 변경, 삭제, 병합, 백업
- **사용자가 "직접실행"을 명시한 경우 — 범위 무관하게 직접 실행**
- **사용자가 캡처/이미지를 보며 실시간 피드백으로 위치·크기를 조정하는 경우 — 직접 실행 허용**

> 모듈별 직접실행 세부 기준(산출물 수 임계값, 허용 도구 등)은 `modules/<module>/SKILL.md` 참조.

**파이프라인 실행 규칙:**
- **Executor/Reviewer는 step 정보만 수신** — 전체 Sprint_Contract 전달 금지 (isolation 위반)
- **병렬→순차 전환 금지** — 병렬 실행 합의 후 사용자 동의 없이 순차 변경 금지
- **MCP 불가 항목 즉시 보고** — 무단 대체 금지

### 파일 관리 규칙

- 원본 파일 외에 백업/수정본을 자동 생성하지 않는다
- 모든 작업 중간 결과는 `.pipeline/` 폴더에만 저장한다
- `results/` 폴더에는 최종 산출물만 유지한다 (중간 버전 금지)
- `.gitignore`에 `*_FIXED*.pptx`, `*_REVIEWED*.pptx`, `*_BACKUP*.pptx` 패턴 등록됨

### .pipeline/ 수명 관리

`.pipeline/` 덤프 파일은 자동으로 쌓인다. 주기적으로 정리한다:

```bash
bash scripts/pipeline_cleanup.sh            # dry-run (삭제 대상 확인)
bash scripts/pipeline_cleanup.sh --execute  # 실제 삭제
```

정책: 실행 디렉토리 7일, requests/suggestions/ 3일, 장기 보관 30일

---

## 파이프라인 실행

@.claude/docs/pipeline-orchestration.md

---

## Hooks / 크로스플랫폼

**Hooks** — `.claude/settings.json`에 정의:
- `SessionStart`: 파이프라인 리마인더
- `PreToolUse(Bash)`: `scripts/agents/guardian.sh`로 위험 명령 차단
- `PostToolUse(Edit|Write)`: `scripts/agents/kairos.sh` lint
- `Stop`: 파이프라인 준수 여부 prompt 검증

**크로스플랫폼** — 설정 흐름: Claude Code → Kiro/Antigravity (단방향, 역방향 금지)
수동 동기화: `/sync-platforms` skill 또는 `bash scripts/agents/sync_pipeline.sh --from claude_code --to all`
