# Requirements Document

## Introduction

하네스 엔지니어링 기반 멀티 에이전트 파이프라인(project-steer)의 설계 요구사항 문서이다. 본 시스템은 7개 업무 모듈(pptx, docx, wbs, trello, dooray, gdrive, datadog)의 산출물을 자동 생성·검증하며, Claude Code 기반 Primary 플랫폼에서 Kiro/Antigravity/VS Code 크로스 플랫폼을 지원한다. `specs/ai-agent-engineering-spec-2026.md`의 23개 기술 요구사항과 `requirements.md`의 프로젝트 적용 사항을 통합하여 EARS 패턴 및 INCOSE 품질 규칙에 따라 정의한다.

## Glossary

- **Orchestrator**: 에이전트 간 파일 기반 통신을 조율하고 I/O만 담당하는 메인 프로세스. `scripts/orchestrate.sh`로 구현된다.
- **Planner**: 사용자 요청을 분석하여 Sprint_Contract JSON으로 확장하는 에이전트. `skills/planner/SKILL.md`에 역할이 정의된다.
- **Executor**: Sprint_Contract에 따라 실제 산출물을 생성하는 에이전트. `skills/executor/SKILL.md`에 역할이 정의된다.
- **Reviewer**: Executor의 결과물을 독립적·적대적으로 검증하는 에이전트. `skills/reviewer/SKILL.md`에 역할이 정의된다.
- **Guardian**: 위험 명령을 Pattern_Matcher로 사전 차단하는 에이전트. Claude API 호출 없이 정규식만으로 동작한다.
- **Coordinator**: Orchestrator의 서브 모듈로, Agent_Team 모드에서만 활성화되어 Specialist 에이전트들의 작업을 분배·통합한다.
- **Sprint_Contract**: Planner가 생성하고 Executor와 Reviewer가 합의하는 에이전트 간 작업 계약 JSON 파일. `schemas/sprint_contract.schema.json`에 스키마가 정의된다.
- **Handoff_File**: 에이전트 간 통신에 사용되는 JSON 기반 파일. `schemas/handoff_file.schema.json`에 스키마가 정의된다.
- **Verdict**: Reviewer가 생성하는 검증 결과 JSON. `schemas/verdict.schema.json`에 스키마가 정의된다.
- **Confidence_Trigger**: 작업의 위험도·복잡도를 4차원(ambiguity, domain_complexity, stakes, context_dependency)으로 평가하여 파이프라인 모드를 결정하는 점수 체계.
- **Feedback_Loop**: Reviewer의 Verdict가 fail일 때 Executor에게 수정을 요청하는 반복 구조.
- **Context_Reset**: 장기 실행 시 컨텍스트 윈도우를 완전히 리셋하고 파일시스템 상태에서 재시작하는 전략.
- **Atomic_Write**: 파일 쓰기 시 임시 파일(.tmp)에 먼저 쓰고 mv로 원자적 교체하는 패턴.
- **IDE_Adapter**: 런타임에 현재 IDE 환경(Kiro, Claude Code, Antigravity, VS Code)을 감지하고 경로를 매핑하는 어댑터 모듈. `scripts/agents/ide_adapter.sh`로 구현된다.
- **Sync_Pipeline**: IDE 간 설정을 단방향(Claude Code → Kiro/Antigravity)으로 동기화하는 파이프라인. `scripts/agents/sync_pipeline.sh`로 구현된다.
- **Git_Worktree**: git worktree를 사용하여 에이전트별 독립 작업 디렉토리를 생성하는 병렬 실행 전략.
- **Auto_Dream**: 파이프라인 완료 후 메모리 파일을 주기적으로 자동 정리하는 서브 에이전트.
- **KAIROS_Monitor**: 파일 변경 시 경량 사전 감시(lint-level)를 수행하는 에이전트. Reviewer의 전체 검증과 범위가 분리된다.
- **UltraPlan**: Confidence_Trigger 점수 0.50 미만에서 활성화되어 복잡한 작업을 계층적 태스크 트리로 분해하는 고급 플래닝 전략.
- **Agent_Team**: 여러 독립 에이전트가 각자 컨텍스트 윈도우를 갖고 병렬 작업하는 협업 패턴.
- **Harness_Subtraction**: 모델 성능 향상에 따라 하네스에서 불필요한 스캐폴딩을 주기적으로 제거하는 최적화 전략.
- **SDD (Spec-Driven Development)**: 실행 가능한 스펙을 먼저 작성하고, 에이전트가 스펙에 따라 코드를 생성하며, 스펙 준수를 자동 검증하는 개발 방법론.
- **Pattern_Matcher**: Guardian이 위험 명령을 탐지하는 데 사용하는 정규식 기반 스크립트. exit code 2로 차단, exit code 0으로 허용한다.
- **MCP_Server**: 모듈별 외부 도구 연동을 위한 Model Context Protocol 서버. `scripts/mcp-toggle.sh`로 on/off 토글한다.
- **Pipeline_Module**: 7개 업무 도메인(pptx, docx, wbs, trello, dooray, gdrive, datadog) 각각을 의미하며, `modules/{name}/SKILL.md`에 정의된다.

## Requirements

### Requirement 1: Orchestrator 프로세스 — 파이프라인 조율

**User Story:** 개발자로서, 에이전트 간 통신을 조율하는 중앙 Orchestrator가 필요하다. 이를 통해 각 에이전트가 독립적으로 실행되면서도 일관된 워크플로우를 유지할 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 작업 요청을 제출하면, THE Orchestrator SHALL 요청을 파싱하여 IDE_Adapter가 반환하는 에이전트 디렉토리의 `requests/` 하위에 Handoff_File을 생성한다.
2. THE Orchestrator SHALL 에이전트 실행 순서를 Planner → Executor → Reviewer 순서로 조율한다.
3. WHEN Agent_Team 모드가 활성화되면, THE Orchestrator SHALL Coordinator 서브 모듈을 통해 Specialist 에이전트들의 작업을 분배한다.
4. WHEN 에이전트 실행이 완료되면, THE Orchestrator SHALL 해당 에이전트의 출력 Handoff_File을 읽고 다음 에이전트에게 전달한다.
5. IF 에이전트 실행 중 타임아웃(120초 초과)이 발생하면, THEN THE Orchestrator SHALL 해당 에이전트의 실행을 중단하고 에러 상태를 Handoff_File에 기록한다.
6. THE Orchestrator SHALL 자체적으로 코드 생성이나 검증 로직을 수행하지 않고, I/O 조율에만 집중한다.
7. WHEN 전체 파이프라인이 완료되면, THE Orchestrator SHALL 최종 결과 요약을 에이전트 디렉토리의 `results/` 하위에 기록한다.
8. THE Orchestrator SHALL 각 에이전트 실행 시 Context_Reset 전략을 적용하여, 이전 에이전트의 컨텍스트를 공유하지 않고 클린 컨텍스트에서 시작한다.

### Requirement 2: Planner 에이전트 — 실행 계획 생성

**User Story:** 개발자로서, 사용자의 자연어 요청을 구조화된 Sprint_Contract로 변환하는 Planner가 필요하다. 이를 통해 Executor가 명확한 지시에 따라 산출물을 생성할 수 있다.

#### Acceptance Criteria

1. WHEN 사용자 요청 Handoff_File을 수신하면, THE Planner SHALL 요청을 분석하여 Sprint_Contract JSON 파일을 에이전트 디렉토리의 `contracts/` 하위에 생성한다.
2. THE Sprint_Contract SHALL 다음 필드를 포함한다: 작업 목표(goal), 대상 모듈(module), 수정 대상 파일 목록(files), 인수 조건(acceptance_criteria), 제약 조건(constraints), 식별된 리스크(risks).
3. THE Planner SHALL 프로젝트의 기존 디렉토리 구조와 대상 모듈의 `SKILL.md`를 분석하여 Sprint_Contract에 반영한다.
4. WHEN Sprint_Contract 생성이 완료되면, THE Planner SHALL 완료 상태를 Handoff_File에 기록한다.
5. THE Planner SHALL 독립 Agent_Session으로 실행되며, Executor 및 Reviewer의 컨텍스트를 공유하지 않는다.
6. THE Planner SHALL 1-4문장의 사용자 요청을 야심적인 범위의 상세 실행 스펙으로 확장하되, 세부 기술 구현은 과도하게 명시하지 않는다.

### Requirement 3: Executor 에이전트 — 산출물 생성

**User Story:** 개발자로서, Sprint_Contract에 따라 실제 산출물을 생성하는 독립 Executor가 필요하다. 이를 통해 산출물 생성과 검증이 분리된다.

#### Acceptance Criteria

1. WHEN Sprint_Contract를 수신하면, THE Executor SHALL 계약에 명시된 파일 목록과 인수 조건에 따라 산출물을 생성한다.
2. THE Executor SHALL 생성한 산출물을 프로젝트 디렉토리에 작성하고, 변경 사항 목록을 에이전트 디렉토리의 `outputs/` 하위 Handoff_File에 기록한다.
3. THE Executor SHALL 대상 모듈의 `SKILL.md`에 정의된 워크플로우와 규칙을 준수한다.
4. THE Executor SHALL 독립 Agent_Session으로 실행되며, Planner 및 Reviewer의 컨텍스트를 공유하지 않는다.
5. WHEN Reviewer로부터 needs_revision Verdict를 수신하면, THE Executor SHALL Reviewer의 issues와 suggestions를 기반으로 산출물을 수정하고 새로운 Handoff_File을 생성한다.
6. IF Feedback_Loop가 Confidence_Trigger에 의해 결정된 최대 횟수를 초과하면, THEN THE Executor SHALL 수정을 중단하고 실패 상태를 Orchestrator에 보고한다.
7. THE Executor SHALL 자기 평가를 수행하지 않는다. 품질 판정은 Reviewer의 역할이다.

### Requirement 4: Reviewer 에이전트 — 적대적 독립 검증

**User Story:** 개발자로서, Executor가 생성한 산출물을 독립적으로 검증하는 Reviewer가 필요하다. 이를 통해 자기 검증 편향 없이 객관적인 품질 평가가 가능하다.

#### Acceptance Criteria

1. WHEN Executor의 출력 Handoff_File을 수신하면, THE Reviewer SHALL Sprint_Contract의 인수 조건 각 항목에 대해 pass 또는 fail 판정을 수행한다.
2. THE Reviewer SHALL 대상 모듈의 `SKILL.md` metadata.checklist에 정의된 기준으로 체크리스트 평가를 수행한다.
3. THE Reviewer SHALL 독립 Agent_Session으로 실행되며, Executor의 내부 reasoning이나 의도를 수신하지 않는다.
4. THE Reviewer SHALL Verdict JSON을 생성한다. Verdict는 verdict(approved/needs_revision/rejected), score(0.0-1.0), checklist_results, issues, suggestions 필드를 포함한다.
5. WHEN score가 0.7 이상이고 critical issue가 없으면, THE Reviewer SHALL approved Verdict를 생성한다.
6. WHEN 검증 결과에 fail 항목이 존재하면, THE Reviewer SHALL 실패 사유와 구체적인 위치 정보를 포함한 수정 제안을 Verdict에 기록한다.
7. THE Reviewer SHALL 이전 리뷰 결과를 수신하지 않는다. 이를 통해 앵커링 편향을 방지한다.
8. THE Reviewer SHALL few-shot 보정을 통해 관대한 평가 편향(leniency bias)을 방지한다.

### Requirement 5: Guardian 에이전트 — 위험 명령 사전 차단

**User Story:** 개발자로서, 위험한 명령이 실행되기 전에 사전 차단하는 Guardian이 필요하다. 이를 통해 개발 환경의 안전성을 보장할 수 있다.

#### Acceptance Criteria

1. WHEN 쉘 명령 실행 요청이 발생하면, THE Guardian SHALL Pattern_Matcher 스크립트를 실행하여 위험 명령을 탐지한다.
2. THE Guardian SHALL 다음 명령을 무조건 차단한다(exit code 2 반환): `DROP DATABASE`, `DROP SCHEMA`, 시스템 네임스페이스에 대한 `kubectl delete namespace`, `rm -rf /` 또는 시스템 디렉토리 삭제, `git push --force` to main/master.
3. THE Guardian SHALL 다음 명령에 대해 경고를 생성한다(exit code 0 + 경고 메시지): `DROP TABLE`, `TRUNCATE`, 사용자 네임스페이스에 대한 `kubectl delete`, `docker compose down -v`.
4. THE Guardian SHALL Claude API 호출 없이 Pattern_Matcher 정규식 로직만으로 위험 명령을 탐지한다. 이를 통해 API 비용 없이 200ms 이내 안전성 검증을 수행한다.
5. IF 차단 대상 명령이 탐지되면, THEN THE Guardian SHALL 실행을 거부하고 차단 사유를 stderr에 출력하며 exit code 2를 반환한다.
6. WHEN 명령이 안전하다고 판정되면, THE Guardian SHALL exit code 0을 반환하여 실행을 허용한다.

### Requirement 6: 파일 기반 에이전트 간 통신

**User Story:** 개발자로서, 에이전트 간 통신이 파일 기반으로 이루어져야 한다. 이를 통해 에이전트 간 컨텍스트 격리를 보장하고 통신 내역을 추적할 수 있다.

#### Acceptance Criteria

1. THE Harness SHALL IDE_Adapter가 반환하는 에이전트 디렉토리 하위에 다음 서브 디렉토리를 사용한다: `requests/`, `contracts/`, `outputs/`, `verdicts/`, `results/`, `plans/`, `suggestions/`, `metrics/`, `reports/`, `archive/`.
2. THE Handoff_File SHALL JSON 형식이며, 다음 공통 필드를 포함한다: `id`(UUID), `timestamp`(ISO 8601), `from_agent`, `to_agent`, `status`(pending/completed/failed), `payload`.
3. WHEN 에이전트가 Handoff_File을 생성하면, THE Harness SHALL 파일명에 타임스탬프와 에이전트 이름을 포함하여 고유성을 보장한다.
4. WHILE 파이프라인이 활성 실행 중인 동안, THE Harness SHALL Handoff_File을 불변(immutable)으로 유지한다.
5. IF Handoff_File의 JSON 파싱에 실패하면, THEN THE Harness SHALL 파싱 에러를 로그에 기록하고 해당 에이전트에 재생성을 요청한다.
6. THE Harness SHALL 모든 파일 쓰기에 Atomic_Write 패턴을 적용한다. 임시 파일(.tmp)에 먼저 쓰고 mv로 원자적 교체하여 동시 접근 시 JSON 손상을 방지한다.
7. FOR ALL Handoff_File JSON 데이터, `schemas/handoff_file.schema.json`으로 파싱한 후 다시 직렬화하면 동일한 구조를 유지한다 (round-trip property).

### Requirement 7: 독립 Agent_Session 관리

**User Story:** 개발자로서, 각 에이전트가 독립된 세션으로 실행되어야 한다. 이를 통해 에이전트 간 컨텍스트 오염을 방지할 수 있다.

#### Acceptance Criteria

1. THE Harness SHALL 각 에이전트(Planner, Executor, Reviewer)를 별도의 프로세스 호출로 실행한다. Claude Code에서는 `claude --print`, Kiro에서는 `invokeSubAgent`를 사용한다.
2. THE Agent_Session SHALL 해당 에이전트의 역할 전용 시스템 프롬프트(`skills/{role}/SKILL.md`)만 포함하며, 다른 에이전트의 대화 이력을 포함하지 않는다.
3. WHEN Agent_Session을 생성할 때, THE Harness SHALL `scripts/agents/call_agent.sh`를 통해 플랫폼을 자동 감지하고 적절한 CLI(claude/gemini)로 라우팅한다.
4. IF 에이전트 호출이 실패하면, THEN THE Harness SHALL 최대 2회 재시도하고, 재시도 실패 시 에러 상태를 Orchestrator에 보고한다.
5. THE Harness SHALL 각 Agent_Session에 Context_Reset 전략을 적용하여 클린 컨텍스트에서 시작한다.

### Requirement 8: Feedback_Loop — 자동 수정 반복

**User Story:** 개발자로서, Reviewer의 검증 실패 시 Executor에게 자동으로 수정을 요청하는 피드백 루프가 필요하다.

#### Acceptance Criteria

1. WHEN Reviewer가 needs_revision Verdict를 생성하면, THE Orchestrator SHALL Verdict의 issues와 suggestions를 Executor에게 전달하여 수정을 요청한다.
2. THE Feedback_Loop SHALL Confidence_Trigger 동작 구간에 따라 최대 반복 횟수를 결정한다: 0.70-0.84 구간은 3회, 0.50-0.69 및 0.50 미만 구간은 5회.
3. WHEN Feedback_Loop가 실행될 때마다, THE Orchestrator SHALL 반복 횟수(iteration)를 Handoff_File에 기록한다.
4. IF 최대 반복 횟수에 도달하면, THEN THE Orchestrator SHALL 파이프라인을 중단하고 마지막 Verdict와 함께 실패 결과를 기록한다.
5. WHEN 동일 이슈가 2회 연속 발생하면, THE Orchestrator SHALL 순환 피드백(circular feedback)을 감지하고 사용자에게 에스컬레이션한다.
6. THE Feedback_Loop SHALL 각 반복마다 Executor에게 새로운 클린 Agent_Session을 생성한다.

### Requirement 9: Confidence_Trigger 기반 파이프라인 모드 결정

**User Story:** 개발자로서, 작업의 위험도와 복잡도에 따라 파이프라인 실행 모드를 자동으로 결정하는 메커니즘이 필요하다.

#### Acceptance Criteria

1. WHEN 사용자 요청을 수신하면, THE Orchestrator SHALL `scripts/agents/confidence_trigger.sh`를 실행하여 작업의 위험도를 평가한다.
2. THE Confidence_Trigger SHALL 4가지 차원으로 점수를 산출한다: 모호성(ambiguity), 도메인 복잡도(domain_complexity), 위험도(stakes), 컨텍스트 의존성(context_dependency). 각 차원은 0.0-1.0 범위이다.
3. WHEN 종합 점수가 0.85 이상이면, THE Orchestrator SHALL 단일 에이전트 모드로 실행한다.
4. WHEN 종합 점수가 0.70-0.84이면, THE Orchestrator SHALL 멀티 에이전트 축소 모드(Feedback_Loop 최대 3회)로 실행한다.
5. WHEN 종합 점수가 0.50-0.69이면, THE Orchestrator SHALL 멀티 에이전트 전체 모드(Feedback_Loop 최대 5회)로 실행한다.
6. WHEN 종합 점수가 0.50 미만이면, THE Orchestrator SHALL 멀티 에이전트 전체 모드에 UltraPlan을 활성화하여 실행한다.
7. THE Confidence_Trigger SHALL 보안 관련 작업(인증, 권한, 암호화, 삭제)에 대해 자동으로 0.70 미만 점수를 부여하여 전체 파이프라인을 강제한다.

### Requirement 10: IDE_Adapter — 런타임 환경 감지 및 경로 매핑

**User Story:** 개발자로서, 하네스가 런타임에 현재 IDE 환경을 감지하고 IDE별로 다른 설정 파일 경로, 훅 포맷, 스티어링 구조를 자동으로 적용해야 한다.

#### Acceptance Criteria

1. WHEN Harness가 초기화되면, THE IDE_Adapter SHALL 런타임 환경 변수 및 프로세스 정보를 분석하여 현재 IDE 환경을 감지한다. 감지 기준: Kiro는 `KIRO_IDE` 환경 변수 또는 `.kiro/` 존재, Claude Code는 `CLAUDE_CODE` 환경 변수, Antigravity는 `ANTIGRAVITY` 환경 변수 또는 `.antigravity/` 존재, VS Code는 `VSCODE_PID` 환경 변수 또는 `.vscode/` 존재.
2. THE IDE_Adapter SHALL IDE별 설정 파일 경로를 매핑한다: Claude Code는 `CLAUDE.md` + `.claude/hooks/` + `.mcp.json`, Kiro는 `AGENTS.md` + `.kiro/steering/` + `.kiro/settings/mcp.json`, Antigravity는 `AGENTS.md` + `.agent/rules/` + `.agent/workflows/`, VS Code는 `AGENTS.md` + `.vscode/tasks.json`.
3. THE IDE_Adapter SHALL 에이전트 디렉토리 구조(`requests/`, `contracts/`, `outputs/`, `verdicts/`, `results/`, `plans/`, `suggestions/`, `metrics/`, `reports/`, `archive/`)를 자동 생성하는 `ensure_agent_dirs` 함수를 제공한다.
4. THE IDE_Adapter SHALL Atomic_Write 함수를 제공하여 모든 에이전트 스크립트가 안전한 파일 쓰기를 수행한다.
5. IF IDE 환경 감지에 실패하면, THEN THE IDE_Adapter SHALL 기본값으로 Kiro 환경을 사용하고 경고를 stderr에 출력한다.

### Requirement 11: Sync_Pipeline — IDE 간 설정 동기화

**User Story:** 개발자로서, Claude Code에서 변경한 하네스 설정을 Kiro/Antigravity에 자동 동기화하는 파이프라인이 필요하다.

#### Acceptance Criteria

1. THE Sync_Pipeline SHALL Claude Code의 `.mcp.json` MCP 서버 상태를 Kiro의 `.kiro/settings/mcp.json`으로 단방향 동기화한다.
2. THE Sync_Pipeline SHALL Claude Code의 `.mcp.json` MCP 서버 상태를 사용자 레벨 Kiro 설정(`~/.kiro/settings/mcp.json`)으로 동기화한다.
3. THE Sync_Pipeline SHALL `--from` 및 `--to` 인자를 받아 동기화 방향을 지정한다.
4. THE Sync_Pipeline SHALL `--status` 인자로 모든 IDE 설정 파일의 존재 여부를 확인한다.
5. THE Sync_Pipeline SHALL 역방향 동기화(Kiro/Antigravity → Claude Code)를 수행하지 않는다.
6. WHEN Claude Code의 설정 파일이 변경되면, THE `.claude/hooks/sync-to-platforms.sh` Hook SHALL 자동으로 Kiro 설정을 동기화한다.

### Requirement 12: MCP 서버 토글 관리

**User Story:** 개발자로서, 작업 시작 전 필요한 MCP 서버만 활성화하고 완료 후 비활성화하여 리소스를 효율적으로 관리해야 한다.

#### Acceptance Criteria

1. THE Harness SHALL `scripts/mcp-toggle.sh`를 통해 MCP 서버를 on/off 토글한다.
2. WHEN 파이프라인이 시작되면, THE Orchestrator SHALL 대상 모듈에 매핑된 MCP 서버를 활성화한다. 매핑: pptx→pptx, docx→docx, trello→trello, dooray→dooray, datadog→datadog, gdrive→google-workspace.
3. WHEN 파이프라인이 완료되면, THE Orchestrator SHALL 활성화했던 MCP 서버를 비활성화한다.
4. THE MCP_Toggle SHALL Primary 설정(`.mcp.json`)을 변경한 후 Kiro 설정(`.kiro/settings/mcp.json`)에 단방향 동기화한다.
5. THE MCP_Toggle SHALL `status` 명령으로 모든 MCP 서버의 현재 상태를 표시한다.

### Requirement 13: Sprint_Contract 스키마 및 검증

**User Story:** 개발자로서, 에이전트 간 합의 문서인 Sprint_Contract의 구조가 명확히 정의되고 검증되어야 한다.

#### Acceptance Criteria

1. THE Sprint_Contract SHALL `schemas/sprint_contract.schema.json`에 정의된 JSON 스키마를 따른다. 필수 필드: task(문자열), module(enum: pptx/docx/wbs/trello/dooray/gdrive/datadog), steps(배열), acceptance_criteria(배열), risks(배열).
2. THE `steps` 배열 각 항목 SHALL 다음 필드를 포함한다: id(정수), action(문자열), acceptance_criteria(문자열 배열). 선택 필드: dependencies(정수 배열), estimated_complexity(low/medium/high).
3. THE Sprint_Contract SHALL 에이전트 디렉토리의 `contracts/` 하위에 `{timestamp}_{contract_id}.json` 형식으로 저장된다.
4. IF Sprint_Contract JSON이 스키마 검증에 실패하면, THEN THE Orchestrator SHALL Planner에게 재생성을 요청한다.
5. FOR ALL 유효한 Sprint_Contract JSON 데이터, `schemas/sprint_contract.schema.json`으로 파싱한 후 다시 직렬화하면 동일한 구조를 유지한다 (round-trip property).

### Requirement 14: Verdict 스키마 및 검증

**User Story:** 개발자로서, Reviewer의 검증 결과인 Verdict의 구조가 명확히 정의되고 검증되어야 한다.

#### Acceptance Criteria

1. THE Verdict SHALL `schemas/verdict.schema.json`에 정의된 JSON 스키마를 따른다. 필수 필드: verdict(enum: approved/needs_revision/rejected), score(0.0-1.0), issues(문자열 배열), suggestions(문자열 배열).
2. WHEN verdict가 needs_revision이면, THE Verdict SHALL 최소 하나의 issue 항목을 포함한다.
3. WHEN verdict가 approved이면, THE Verdict SHALL score 0.7 이상을 가진다.
4. THE Verdict SHALL 에이전트 디렉토리의 `verdicts/` 하위에 저장된다.
5. FOR ALL 유효한 Verdict JSON 데이터, `schemas/verdict.schema.json`으로 파싱한 후 다시 직렬화하면 동일한 구조를 유지한다 (round-trip property).

### Requirement 15: 비용 및 토큰 관리

**User Story:** 개발자로서, 멀티 에이전트 파이프라인의 API 비용을 모니터링하고 제어할 수 있어야 한다.

#### Acceptance Criteria

1. THE Harness SHALL 각 Agent_Session의 입력/출력 토큰 수를 Handoff_File의 `token_usage` 필드에 기록한다.
2. WHEN 파이프라인이 완료되면, THE `scripts/agents/token_tracker.sh` SHALL 전체 파이프라인의 총 토큰 사용량과 예상 비용(USD)을 결과 요약에 포함한다.
3. THE Harness SHALL 파이프라인당 최대 토큰 예산을 설정할 수 있는 구성 파일(`config/token_budget.json`)을 지원한다.
4. IF 토큰 예산의 80%에 도달하면, THEN THE Orchestrator SHALL 경고를 로그에 기록한다.
5. IF 토큰 예산을 초과하면, THEN THE Orchestrator SHALL 현재 에이전트의 실행을 완료한 후 파이프라인을 중단하고 부분 결과를 기록한다.

### Requirement 16: Git_Worktree 기반 병렬 에이전트 실행

**User Story:** 개발자로서, 여러 Executor 에이전트가 동시에 다른 기능을 병렬로 개발할 수 있어야 한다.

#### Acceptance Criteria

1. WHEN 복수의 Sprint_Contract가 독립적이면(수정 대상 파일이 겹치지 않으면), THE Orchestrator SHALL 각 Executor에게 별도의 Git_Worktree를 할당하여 병렬 실행한다.
2. THE Harness SHALL `scripts/agents/git_worktree.sh create <branch>` 명령으로 에이전트별 임시 브랜치와 작업 디렉토리를 생성한다.
3. WHEN 병렬 Executor가 모두 완료되면, THE Orchestrator SHALL 자동 게이트(JSON 검증)를 통과한 브랜치만 순차적으로 main에 머지한다.
4. IF 머지 시 충돌이 발생하면, THEN THE Orchestrator SHALL 충돌 내역을 Handoff_File에 기록하고 사용자에게 수동 해결을 요청한다.
5. WHEN 병렬 실행이 완료되면, THE Harness SHALL `scripts/agents/git_worktree.sh remove <branch>`로 임시 작업 디렉토리를 정리한다.
6. THE Orchestrator SHALL 동일 파일을 수정하는 Sprint_Contract들은 병렬 실행하지 않고 순차 실행한다.

### Requirement 17: Auto_Dream 메모리 자동 정리

**User Story:** 개발자로서, 장기 프로젝트에서 에이전트 메모리 파일이 자동으로 정리되어야 한다.

#### Acceptance Criteria

1. THE `scripts/agents/auto_dream.sh` SHALL 에이전트 디렉토리의 메모리 파일을 정리한다.
2. THE Auto_Dream SHALL 7일 이상 경과한 completed 상태의 Handoff_File을 `archive/` 디렉토리로 이동한다.
3. THE Auto_Dream SHALL 중복된 Handoff_File(동일 MD5 해시)을 탐지하고 `archive/duplicates/`로 이동한다.
4. THE Auto_Dream SHALL 5개 이상의 JSON 파일이 누적된 후에만 실행된다.
5. WHEN Auto_Dream 실행이 완료되면, THE Harness SHALL 정리 결과 요약(스캔 수, 아카이브 수, 중복 제거 수)을 로그에 기록한다.
6. WHILE 파이프라인이 활성 실행 중인 동안, THE Auto_Dream SHALL 실행되지 않는다. 파이프라인 완료 후에만 아카이브를 수행한다.

### Requirement 18: KAIROS 경량 사전 감시

**User Story:** 개발자로서, 파일 변경 시 경량 사전 감시를 수행하여 빠른 피드백을 받을 수 있어야 한다.

#### Acceptance Criteria

1. WHEN 코드 파일이 변경되면, THE `scripts/agents/kairos.sh` SHALL 변경된 파일에 대해 경량 사전 감시(lint-level)를 실행한다.
2. THE KAIROS_Monitor SHALL 파일 확장자별 검사를 수행한다: Python은 구문 검사(`py_compile`), JavaScript는 `node --check`, JSON은 파싱 검사, Shell은 `bash -n` 구문 검사.
3. THE KAIROS_Monitor SHALL 모든 파일에 대해 민감 정보 패턴(api_key, password, token 등의 하드코딩)을 검사한다.
4. IF 분석 결과 문제가 발견되면, THEN THE KAIROS_Monitor SHALL 제안 사항을 에이전트 디렉토리의 `suggestions/` 하위에 JSON으로 기록한다.
5. THE KAIROS_Monitor SHALL Reviewer의 전체 검증 파이프라인과 범위가 분리된다: KAIROS는 단일 파일 수준의 빠른 피드백, Reviewer는 전체 프로젝트 수준의 종합 검증.

### Requirement 19: UltraPlan 계층적 태스크 분해

**User Story:** 개발자로서, 복잡한 작업을 자동으로 계층적 태스크 트리로 분해하는 고급 플래닝이 필요하다.

#### Acceptance Criteria

1. WHEN Confidence_Trigger 점수가 0.50 미만이면, THE Planner SHALL `scripts/agents/ultraplan.sh`를 통해 UltraPlan 전략을 활성화하여 계층적 태스크 트리를 생성한다.
2. THE UltraPlan SHALL 최상위 목표를 하위 목표(sub_goals)로 분해하고, 각 하위 목표를 독립적인 Sprint_Contract로 변환한다.
3. THE UltraPlan SHALL 하위 목표 간 의존성 그래프(dependency_graph)를 생성하여, 독립적인 목표는 병렬 실행(Git_Worktree)하고 의존적인 목표는 순차 실행한다.
4. THE UltraPlan SHALL 최대 3단계 깊이까지 분해하며, 각 리프 태스크는 단일 Sprint_Contract로 실행 가능한 크기여야 한다.
5. WHEN UltraPlan이 완료되면, THE Planner SHALL 태스크 트리와 의존성 그래프를 에이전트 디렉토리의 `plans/` 하위에 JSON 형식으로 저장한다.

### Requirement 20: SDD (Spec-Driven Development) 통합

**User Story:** 개발자로서, 하네스가 프로젝트의 스펙 문서와 통합되어 스펙 기반 개발을 자동화해야 한다.

#### Acceptance Criteria

1. WHEN 프로젝트에 `requirements.md`가 존재하면, THE `scripts/agents/sdd_integrator.sh` SHALL 모듈별 인수 조건을 자동으로 추출한다.
2. THE SDD_Integrator SHALL 추출된 인수 조건을 Sprint_Contract의 acceptance_criteria로 변환한다.
3. THE Reviewer SHALL 스펙 문서의 인수 조건을 자동으로 추출하여 Verdict의 검증 기준으로 사용한다.
4. IF 스펙과 구현 간 드리프트(drift)가 감지되면, THEN THE Reviewer SHALL 드리프트 항목을 Verdict에 기록하고 Executor에게 수정을 요청한다.

### Requirement 21: Agent_Team 협업 패턴

**User Story:** 개발자로서, 여러 전문화된 에이전트가 팀으로 협업하여 복잡한 다중 모듈 작업을 처리할 수 있어야 한다.

#### Acceptance Criteria

1. WHEN 작업 요청에 복수의 모듈이 지정되면(쉼표 구분), THE `scripts/agents/agent_team.sh` SHALL Agent_Team 모드를 활성화한다.
2. THE Agent_Team SHALL 각 모듈별로 독립된 Sprint_Contract를 생성한다(Step 1: Planning per module).
3. THE Agent_Team SHALL 각 모듈별로 독립된 Executor를 실행한다(Step 2: Executing per module).
4. THE Agent_Team SHALL 각 모듈별로 독립된 Reviewer 검증을 수행한다(Step 3: Individual review per module).
5. WHEN 모든 모듈의 개별 검증이 완료되면, THE Agent_Team SHALL 통합 결과 요약을 에이전트 디렉토리의 `results/` 하위에 JSON으로 저장한다.
6. THE Agent_Team의 각 Specialist SHALL 독립된 Agent_Session에서 실행되며, 다른 Specialist의 컨텍스트를 공유하지 않는다.

### Requirement 22: Harness_Subtraction — 하네스 최적화

**User Story:** 개발자로서, 모델 성능 향상에 따라 하네스에서 불필요한 스캐폴딩을 주기적으로 제거할 수 있어야 한다.

#### Acceptance Criteria

1. THE `scripts/agents/harness_subtraction.sh` SHALL 각 에이전트 컴포넌트의 기여도를 측정하는 메트릭을 수집한다: Reviewer의 fail 발견 횟수, Guardian의 차단 횟수, Planner의 Sprint_Contract 생성 횟수.
2. WHEN 특정 컴포넌트의 기여도가 30일간 0이면, THE Harness SHALL 해당 컴포넌트의 비활성화를 제안한다. Guardian은 안전성을 위해 항상 유지한다.
3. THE Harness SHALL 에이전트 디렉토리의 `metrics/` 하위에 메트릭을 JSON 형식으로 기록한다.
4. WHEN Harness_Subtraction 분석이 완료되면, THE Harness SHALL 최적화 제안 보고서를 에이전트 디렉토리의 `reports/` 하위에 생성한다.
5. THE Harness SHALL 비활성화된 컴포넌트를 즉시 재활성화할 수 있는 설정을 지원한다.

### Requirement 23: 크로스 플랫폼 Hook 시스템

**User Story:** 개발자로서, Claude Code의 Hook 시스템이 파이프라인 준수를 자동으로 강제하고, 설정 변경 시 다른 플랫폼에 동기화해야 한다.

#### Acceptance Criteria

1. WHEN Claude Code 세션이 시작되면, THE SessionStart Hook SHALL `sync-to-platforms.sh`를 실행하여 설정을 동기화하고 파이프라인 리마인더를 출력한다.
2. WHEN Bash 명령 실행 요청이 발생하면, THE PreToolUse Hook SHALL `scripts/agents/guardian.sh`를 통해 위험 명령을 사전 차단한다.
3. WHEN 파일 편집/쓰기가 완료되면, THE PostToolUse Hook SHALL 설정 파일(`.mcp.json`, `.claude/settings*`) 변경 시 `sync-to-platforms.sh`를 실행하고, 모듈/스킬 파일 변경 시 KAIROS 경량 검사를 실행한다.
4. WHEN Claude Code 세션이 종료되면, THE Stop Hook SHALL 완료된 작업이 하네스 파이프라인을 준수했는지 검증한다.
5. THE Kiro 플랫폼 SHALL `.kiro/steering/multi-agent-pipeline.md` 스티어링 파일을 통해 동일한 파이프라인 규칙을 적용한다.
6. THE Antigravity 플랫폼 SHALL `.agent/rules/pipeline-rules.md`와 `.agent/workflows/` 워크플로우를 통해 동일한 파이프라인 규칙을 적용한다.

### Requirement 24: PPTX 모듈 — 프레젠테이션 생성

**User Story:** 개발자로서, MCP 도구를 통해 JSON 데이터를 직접 전달하여 프레젠테이션을 자동 생성해야 한다.

#### Acceptance Criteria

1. THE PPTX_Module SHALL MCP 도구(pptx 서버)로 JSON 데이터를 직접 전달하여 프레젠테이션을 생성한다. Python 스크립트를 작성하여 생성하지 않는다.
2. THE PPTX_Module SHALL `templates/pptx_template.pptx` 템플릿을 기반으로 8개 레이아웃(표지, 본문, 본문_강조, 본문_프로세스, 목차, 섹션구분, 이미지강조, 끝맺음)을 지원한다.
3. THE PPTX_Module SHALL 표지 → 목차 → 본문(N-N. 제목) → Thank You 구조를 따른다.
4. THE PPTX_Module SHALL 타이틀 영역 4.5인치/28pt 기준 340pt 초과 시 자연스러운 단어 경계에서 줄바꿈(`\n`)을 삽입한다.
5. THE PPTX_Module SHALL `modules/pptx/references/layout-spec.md`에 정의된 shape 좌표(EMU)를 준수한다.

### Requirement 25: DOCX 모듈 — 문서 생성

**User Story:** 개발자로서, 스타일 가이드에 따라 프로젝트 문서를 자동 생성해야 한다.

#### Acceptance Criteria

1. THE DOCX_Module SHALL MCP 도구(docx 서버)를 통해 문서를 생성한다.
2. THE DOCX_Module SHALL `templates/docx_template.docx` 템플릿과 `templates/docx_style_guide.md` 스타일 가이드를 준수한다.
3. THE DOCX_Module SHALL 표지(28pt Bold #1A1A2E) → History → 목차 → 본문 → 푸터(PAGE 9pt) 구조를 따른다.
4. THE DOCX_Module SHALL 테이블 헤더에 #1B3A5C navy + white, 짝수행에 #F2F2F2 배경을 적용한다.
5. THE DOCX_Module SHALL 문체를 현재형 `~한다`로 통일한다.

### Requirement 26: WBS 모듈 — 작업 분해 구조

**User Story:** 개발자로서, Excel 기반 WBS를 자동 생성하고 진척을 추적해야 한다.

#### Acceptance Criteria

1. THE WBS_Module SHALL Excel 기반 WBS를 생성하며, 태스크 계층(Phase → Work Package → Task)을 지원한다.
2. THE WBS_Module SHALL 태스크 간 의존성(FS, FF, SS, SF)을 매핑하고 순환 의존성이 없음을 검증한다.
3. THE WBS_Module SHALL 100% 규칙을 적용한다: 하위 항목이 상위 범위를 완전히 커버한다.
4. THE WBS_Module SHALL 가중 평균 기반으로 상위 항목 진척률을 자동 계산한다.

### Requirement 27: Trello 모듈 — 칸반 보드 관리

**User Story:** 개발자로서, Trello 보드의 카드를 자동으로 관리하고 WBS 태스크와 동기화해야 한다.

#### Acceptance Criteria

1. THE Trello_Module SHALL MCP 도구(trello 서버)를 통해 보드, 리스트, 카드 CRUD를 수행한다.
2. THE Trello_Module SHALL WBS 태스크를 Trello 카드로 변환하고 동기화한다.
3. THE Trello_Module SHALL 카드에 라벨, 담당자, 마감일을 설정한다.
4. THE Trello_Module SHALL 워크플로우 단계별 리스트(Backlog → In Progress → Review → Done)를 관리한다.

### Requirement 28: Dooray 모듈 — 태스크 및 주간보고

**User Story:** 개발자로서, Dooray에서 주간보고를 자동 작성하고 회의록에서 액션 아이템을 추출해야 한다.

#### Acceptance Criteria

1. THE Dooray_Module SHALL MCP 도구(dooray 서버)를 통해 주간보고를 자동 작성하고 발송한다.
2. THE Dooray_Module SHALL WBS와 Trello 데이터를 연동하여 금주 완료/차주 계획을 추출한다.
3. THE Dooray_Module SHALL 회의록에서 액션 아이템을 추출하고 Dooray 태스크로 생성한다.
4. THE Dooray_Module SHALL 관련자 멘션 및 알림을 설정한다.

### Requirement 29: Google Drive 모듈 — 파일 관리

**User Story:** 개발자로서, 산출물을 Google Drive에 자동 업로드하고 폴더 구조를 관리해야 한다.

#### Acceptance Criteria

1. THE GDrive_Module SHALL MCP 도구(google-workspace 서버)를 통해 산출물 업로드 및 다운로드를 수행한다.
2. THE GDrive_Module SHALL 프로젝트 기반 폴더 계층 구조를 생성하고 관리한다.
3. THE GDrive_Module SHALL 네이밍 컨벤션(프로젝트명_날짜_버전)을 적용한다.
4. THE GDrive_Module SHALL 폴더별 공유 권한을 설정한다.

### Requirement 30: Datadog 모듈 — 모니터링 관리

**User Story:** 개발자로서, Datadog 모니터와 대시보드를 자동으로 생성하고 관리해야 한다.

#### Acceptance Criteria

1. THE Datadog_Module SHALL MCP 도구(datadog 서버)를 통해 모니터를 생성하고 임계값 및 알림 라우팅을 설정한다.
2. THE Datadog_Module SHALL 대시보드를 생성하고 위젯별 메트릭 쿼리를 설정한다.
3. THE Datadog_Module SHALL 대시보드 캡처(스크린샷/데이터 추출)를 수행하고 주간 보고용 이미지를 생성한다.
4. THE Datadog_Module SHALL 메트릭 쿼리의 정확성을 검증한다.

### Requirement 31: 에이전트 실행 스크립트 체계

**User Story:** 개발자로서, 각 에이전트를 독립 프로세스로 실행하는 스크립트 체계가 필요하다.

#### Acceptance Criteria

1. THE Harness SHALL `scripts/agents/` 디렉토리에 각 에이전트별 실행 스크립트를 배치한다: `orchestrate.sh`, `call_agent.sh`, `confidence_trigger.sh`, `guardian.sh`, `ide_adapter.sh`, `kairos.sh`, `auto_dream.sh`, `ultraplan.sh`, `token_tracker.sh`, `harness_subtraction.sh`, `agent_team.sh`, `git_worktree.sh`, `sdd_integrator.sh`, `sync_pipeline.sh`.
2. THE `call_agent.sh` SHALL 플랫폼을 자동 감지하여 적절한 CLI로 라우팅한다: Claude Code는 `claude --print`, Antigravity는 `gemini`, 미지원 환경은 가이던스 파일 생성.
3. THE 에이전트 스크립트 SHALL 실행 완료 시 종료 코드 0(성공), 1(비차단 경고), 2(차단/실패)를 반환한다.
4. WHEN 처리되지 않은 예외가 발생하면, THE 스크립트 SHALL 에러 메시지를 stderr에 출력하고 종료 코드 2를 반환한다.
5. THE 에이전트 스크립트 SHALL 모든 파일 쓰기에 IDE_Adapter의 `atomic_write` 함수를 사용한다.

### Requirement 32: 정보 차단 및 컨텍스트 격리

**User Story:** 개발자로서, 에이전트 간 정보 차단이 엄격히 적용되어 자기 확인 편향과 앵커링 편향을 방지해야 한다.

#### Acceptance Criteria

1. THE Orchestrator SHALL Reviewer에게 Executor의 내부 reasoning이나 의도를 전달하지 않는다. Reviewer는 Sprint_Contract(계획)과 실행 결과만 수신한다.
2. THE Orchestrator SHALL Reviewer에게 이전 리뷰 결과를 전달하지 않는다. 이를 통해 앵커링 편향을 방지한다.
3. THE Orchestrator SHALL 각 에이전트를 독립된 컨텍스트에서 실행한다. 에이전트 간 대화 이력을 공유하지 않는다.
4. THE Executor SHALL 자기 평가를 수행하지 않는다. 산출물의 품질 판정은 Reviewer의 독점적 역할이다.
5. THE Harness SHALL Executor와 Reviewer를 하나의 에이전트로 합치지 않는다. 역할 분리를 항상 유지한다.
