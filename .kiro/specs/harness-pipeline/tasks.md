# Implementation Plan: Harness Pipeline

## Overview

하네스 파이프라인의 멀티 에이전트 오케스트레이션 시스템 구현 계획이다. 기존 14개 에이전트 스크립트, 3개 JSON 스키마, 4개 스킬, 7개 모듈이 이미 구현되어 있으므로, 본 태스크는 (A) 기존 스크립트의 버그 수정 및 요구사항 준수 개선, (B) 미구현 기능 추가, (C) Property-Based Test 및 Unit Test 인프라 구축에 집중한다.

기술 스택: Bash + Python (Hypothesis for PBT)

## Tasks

- [ ] 1. 테스트 인프라 구축 및 Guardian 속성 검증
  - [ ] 1.1 테스트 디렉토리 구조 및 Hypothesis 설정
    - `tests/` 디렉토리 생성, `tests/conftest.py`에 공통 fixture 정의
    - `tests/requirements.txt`에 `hypothesis`, `jsonschema`, `pytest` 의존성 명시
    - `pytest.ini` 또는 `pyproject.toml`에 pytest 설정 (최소 100회 반복)
    - _Requirements: 6.7, 13.5, 14.5_

  - [ ] 1.2 Guardian 차단 로직 개선 — 누락 패턴 보강
    - `scripts/agents/guardian.sh`의 BLOCK_PATTERNS에 `chmod -R 777 /` 패턴이 이미 존재하는지 확인하고, 설계 문서의 전체 차단 목록과 대조하여 누락 패턴 보강
    - 경고 패턴(WARN_PATTERNS)에 `rm -rf` 일반 패턴이 경고로 분류되는지 확인 (차단 패턴 `rm -rf /`와 구분)
    - Guardian의 exit code 체계 정리: 설계 문서는 exit 0(허용/경고), exit 2(차단)이나 스크립트 주석에 exit 1(경고)이 혼재 — exit 0 + stderr 경고로 통일
    - _Requirements: 5.2, 5.3, 5.5, 5.6_

  - [ ]* 1.3 Property Test: Guardian이 모든 위험 명령을 차단한다 (Property 1)
    - **Property 1: Guardian blocks all dangerous commands**
    - Hypothesis `@given`으로 차단 패턴 포함 명령 문자열을 생성하여 exit code 2 반환 검증
    - 테스트 파일: `tests/test_guardian_properties.py`
    - **Validates: Requirements 5.2, 5.5**

  - [ ]* 1.4 Property Test: Guardian이 안전/경고 명령을 올바르게 분류한다 (Property 2)
    - **Property 2: Guardian correctly classifies safe and warning commands**
    - 차단 패턴 미포함 명령에 대해 exit code 0 반환, 경고 패턴 포함 시 stderr 경고 메시지 검증
    - 테스트 파일: `tests/test_guardian_properties.py`
    - **Validates: Requirements 5.3, 5.6**

- [ ] 2. Confidence_Trigger 점수 계산 및 모드 매핑 검증
  - [ ] 2.1 Confidence_Trigger 보안 키워드 강제 로직 개선
    - `scripts/agents/confidence_trigger.sh`에서 보안 키워드 탐지 시 stakes=0.8만 설정하는데, 종합 점수가 0.70 이상이 될 수 있는 엣지 케이스 존재
    - 보안 키워드 탐지 시 최종 score를 `min(score, 0.69)`로 클램핑하여 반드시 multi-agent 파이프라인 강제
    - _Requirements: 9.7_

  - [ ]* 2.2 Property Test: Confidence_Trigger 점수 계산 및 모드 매핑 (Property 4)
    - **Property 4: Confidence_Trigger score calculation and mode mapping**
    - Hypothesis로 임의 task 문자열 + 유효 모듈명 생성, score ∈ [0.0, 1.0], 4개 차원 각각 ∈ [0.0, 1.0], mode-score 매핑 일관성 검증
    - 테스트 파일: `tests/test_confidence_trigger_properties.py`
    - **Validates: Requirements 8.2, 9.2, 9.3, 9.4, 9.5, 9.6**

  - [ ]* 2.3 Property Test: 보안 작업에 대한 전체 파이프라인 강제 (Property 5)
    - **Property 5: Confidence_Trigger enforces full pipeline for security tasks**
    - 보안 키워드 포함 task에 대해 score < 0.70 검증
    - 테스트 파일: `tests/test_confidence_trigger_properties.py`
    - **Validates: Requirements 9.7**

- [ ] 3. Checkpoint — 테스트 통과 확인
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. JSON 스키마 검증 및 Verdict 비즈니스 규칙
  - [ ] 4.1 JSON 스키마 round-trip 검증 유틸리티 작성
    - `tests/test_schema_properties.py`에 3개 스키마(sprint_contract, verdict, handoff_file)의 round-trip 검증 로직 구현
    - `jsonschema` 라이브러리로 스키마 유효성 검증 + JSON serialize/deserialize 동등성 확인
    - _Requirements: 6.7, 13.5, 14.5_

  - [ ]* 4.2 Property Test: JSON 스키마 round-trip 보존 (Property 3)
    - **Property 3: JSON schema round-trip preservation**
    - Hypothesis로 각 스키마에 맞는 유효 JSON 데이터를 생성하여 parse → re-serialize 동등성 검증
    - 테스트 파일: `tests/test_schema_properties.py`
    - **Validates: Requirements 6.7, 13.5, 14.5**

  - [ ] 4.3 Verdict 비즈니스 규칙 검증 로직 추가
    - `skills/reviewer/scripts/validate_review.sh`에 비즈니스 규칙 검증 추가: approved → score ≥ 0.7, needs_revision → issues 배열 ≥ 1개
    - 현재 스크립트가 스키마 검증만 수행하는 경우 비즈니스 규칙 검증 Python 로직 추가
    - _Requirements: 14.2, 14.3_

  - [ ]* 4.4 Property Test: Verdict 비즈니스 규칙 일관성 (Property 9)
    - **Property 9: Verdict business rule consistency**
    - Hypothesis로 유효 Verdict JSON 생성, approved → score ≥ 0.7, needs_revision → len(issues) ≥ 1 검증
    - 테스트 파일: `tests/test_verdict_properties.py`
    - **Validates: Requirements 14.2, 14.3**

- [ ] 5. IDE_Adapter 및 Atomic_Write 검증
  - [ ] 5.1 IDE_Adapter 기본값 경고 메시지 추가
    - `scripts/agents/ide_adapter.sh`의 `detect_ide()` 함수에서 기본값(kiro) 선택 시 stderr에 경고 메시지 출력 (현재 누락)
    - 요구사항 10.5: "기본값으로 Kiro 환경을 사용하고 경고를 stderr에 출력"
    - _Requirements: 10.5_

  - [ ]* 5.2 Property Test: IDE_Adapter 감지 및 경로 매핑 일관성 (Property 6)
    - **Property 6: IDE_Adapter detection and path mapping consistency**
    - 환경 변수 조합별 IDE 감지 결과 및 5개 경로 변수 매핑 정확성 검증
    - 테스트 파일: `tests/test_ide_adapter_properties.py`
    - **Validates: Requirements 10.1, 10.2, 10.5**

  - [ ]* 5.3 Property Test: Atomic_Write 파일 내용 정확성 (Property 7)
    - **Property 7: Atomic_Write produces correct file content**
    - Hypothesis로 임의 파일 경로 + 내용 생성, atomic_write 후 파일 내용 일치 검증
    - 테스트 파일: `tests/test_ide_adapter_properties.py`
    - **Validates: Requirements 6.6, 10.4**

- [ ] 6. Orchestrator 순환 피드백 감지 및 정보 차단
  - [ ] 6.1 순환 피드백 감지 로직 개선
    - `scripts/orchestrate.sh`의 순환 피드백 감지가 Python `repr()` 문자열 비교에 의존 — JSON 구조적 비교로 개선
    - `issues` 배열을 정렬 후 JSON 직렬화하여 비교하도록 수정
    - _Requirements: 8.5_

  - [ ] 6.2 Reviewer 정보 차단 검증 강화
    - `scripts/orchestrate.sh`의 Reviewer 입력 구성 부분에서 Executor의 reasoning이 포함되지 않도록 명시적 필터링 추가
    - Reviewer 입력에 Sprint_Contract + 실행 결과만 포함되는지 검증하는 assertion 추가
    - _Requirements: 32.1, 32.2_

  - [ ]* 6.3 Property Test: 순환 피드백 감지 (Property 8)
    - **Property 8: Circular feedback detection**
    - 동일 issues 배열을 가진 연속 Verdict 파일 생성 후 감지 로직 검증
    - 테스트 파일: `tests/test_orchestrator_properties.py`
    - **Validates: Requirements 8.5**

  - [ ]* 6.4 Property Test: Reviewer 정보 차단 (Property 12)
    - **Property 12: Reviewer information barrier**
    - 파이프라인 실행 후 Reviewer 입력 파일에 Executor reasoning/self-assessment 미포함 검증
    - 테스트 파일: `tests/test_orchestrator_properties.py`
    - **Validates: Requirements 32.1, 32.2**

- [ ] 7. Checkpoint — 핵심 속성 테스트 통과 확인
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. MCP Toggle 동기화 및 KAIROS 크리덴셜 감지
  - [ ] 8.1 MCP Toggle 동기화 상태 검증 로직 추가
    - `scripts/mcp-toggle.sh`에 토글 후 `.mcp.json`과 `.kiro/settings/mcp.json`의 disabled 필드 일치 여부를 검증하는 `verify` 서브커맨드 추가
    - _Requirements: 12.4_

  - [ ]* 8.2 Property Test: MCP Toggle 상태 동기화 (Property 10)
    - **Property 10: MCP toggle state synchronization**
    - Hypothesis로 서버명 + 상태(on/off) 생성, 토글 후 두 설정 파일의 disabled 필드 동일성 검증
    - 테스트 파일: `tests/test_mcp_toggle_properties.py`
    - **Validates: Requirements 12.4**

  - [ ] 8.3 KAIROS 크리덴셜 패턴 감지 개선
    - `scripts/agents/kairos.sh`의 민감 정보 패턴에 `AWS_ACCESS_KEY_ID`, `PRIVATE_KEY`, `SECRET_KEY` 패턴 추가
    - 감지 시 severity를 "warn"으로 설정하는 로직이 정확한지 확인
    - _Requirements: 18.3_

  - [ ]* 8.4 Property Test: KAIROS 크리덴셜 패턴 감지 (Property 11)
    - **Property 11: KAIROS credential pattern detection**
    - Hypothesis로 `api_key|password|token` 패턴 포함 파일 생성, KAIROS 실행 후 severity="warn" 이슈 보고 검증
    - 테스트 파일: `tests/test_kairos_properties.py`
    - **Validates: Requirements 18.3**

- [ ] 9. 토큰 예산 관리 및 에이전트 실행 체계 보강
  - [ ] 9.1 토큰 예산 설정 파일 및 예산 초과 로직 구현
    - `config/token_budget.json` 설정 파일 생성 (기본 예산 정의)
    - `scripts/agents/token_tracker.sh`에 예산 80% 경고 및 100% 초과 시 파이프라인 중단 로직 추가
    - `scripts/orchestrate.sh`에 각 에이전트 실행 후 토큰 예산 확인 로직 통합
    - _Requirements: 15.3, 15.4, 15.5_

  - [ ] 9.2 call_agent.sh 재시도 로직 추가
    - `scripts/agents/call_agent.sh`에 에이전트 호출 실패 시 최대 2회 재시도 로직 추가
    - 재시도 실패 시 에러 상태를 Orchestrator에 보고 (exit 2)
    - _Requirements: 7.4_

  - [ ] 9.3 에이전트 스크립트 종료 코드 표준화
    - 모든 에이전트 스크립트(`scripts/agents/*.sh`)의 종료 코드를 표준화: 0(성공), 1(비차단 경고), 2(차단/실패)
    - 처리되지 않은 예외 시 stderr 출력 + exit 2 보장을 위한 `trap` 핸들러 추가
    - _Requirements: 31.3, 31.4_

- [ ] 10. SDD 통합 및 Agent_Team 개선
  - [ ] 10.1 SDD_Integrator 파일 경로 수정
    - `scripts/agents/sdd_integrator.sh`에서 `requirements.md` 경로가 하드코딩 — 프로젝트 루트 또는 `.kiro/specs/` 하위 경로를 인자로 받도록 수정
    - 모듈별 섹션 매핑을 requirements.md의 실제 구조(Requirement 24-30)에 맞게 업데이트
    - _Requirements: 20.1, 20.2_

  - [ ] 10.2 Agent_Team 병렬 실행 지원
    - `scripts/agents/agent_team.sh`의 Step 2(Executing per module)에서 독립 모듈을 `&` 백그라운드 프로세스로 병렬 실행하도록 개선
    - `wait` 명령으로 모든 병렬 프로세스 완료 대기
    - _Requirements: 21.2, 21.3, 21.6_

  - [ ]* 10.3 Unit Test: SDD_Integrator 인수 조건 추출
    - SDD_Integrator가 requirements.md에서 모듈별 인수 조건을 정확히 추출하는지 검증
    - 테스트 파일: `tests/test_sdd_integrator.py`
    - _Requirements: 20.1, 20.2_

- [ ] 11. Orchestrator Handoff_File 생성 및 파이프라인 완성
  - [ ] 11.1 Orchestrator 요청 Handoff_File 생성 추가
    - `scripts/orchestrate.sh`에서 파이프라인 시작 시 `requests/` 하위에 Handoff_File JSON 생성 (현재 누락)
    - Handoff_File에 id(UUID), timestamp, from_agent, to_agent, status, payload 필드 포함
    - _Requirements: 1.1, 6.2, 6.3_

  - [ ] 11.2 에이전트 타임아웃 처리 추가
    - `scripts/agents/call_agent.sh`에 120초 타임아웃 적용 (`timeout 120` 명령 사용)
    - 타임아웃 발생 시 에러 Handoff_File 생성 및 exit 2 반환
    - _Requirements: 1.5_

  - [ ] 11.3 Auto_Dream 활성 파이프라인 보호 로직 추가
    - `scripts/agents/auto_dream.sh`에 활성 파이프라인 실행 중 아카이브 방지 로직 추가
    - `.pipeline/` 하위에 `running.lock` 파일 존재 시 실행 건너뛰기
    - `scripts/orchestrate.sh`에 파이프라인 시작/종료 시 lock 파일 생성/삭제 추가
    - _Requirements: 17.6_

  - [ ]* 11.4 Unit Test: Orchestrator 파이프라인 흐름
    - Orchestrator의 단일 모듈 파이프라인 흐름(CT → Guardian → Planner → Execute-Review Loop) 검증
    - mock 에이전트를 사용한 통합 테스트
    - 테스트 파일: `tests/test_orchestrator_integration.py`
    - _Requirements: 1.2, 1.4, 1.6, 1.7_

- [ ] 12. Smoke Test 및 크로스 플랫폼 검증
  - [ ] 12.1 Smoke Test 스크립트 작성
    - `tests/test_smoke.py`에 모든 에이전트 스크립트 존재 및 실행 가능 여부 검증
    - JSON 스키마 파일 유효성 검증
    - 크로스 플랫폼 설정 파일(CLAUDE.md, AGENTS.md, .kiro/, .gemini/, .agent/) 존재 여부 검증
    - _Requirements: 31.1, 23.5, 23.6_

  - [ ]* 12.2 Unit Test: 크로스 플랫폼 동기화
    - Sync_Pipeline의 Claude Code → Kiro 동기화 검증
    - MCP Toggle의 단방향 동기화 검증
    - 테스트 파일: `tests/test_sync_pipeline.py`
    - _Requirements: 11.1, 11.5, 12.4_

- [ ] 13. Final Checkpoint — 전체 테스트 통과 확인
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- 기존 구현 스크립트 14개는 대부분 동작하나, 요구사항 대비 누락/불일치 사항을 개선
- Property-Based Tests는 Hypothesis (Python)로 작성, 각 Property는 design.md의 12개 Correctness Properties에 1:1 매핑
- 테스트는 bash 스크립트를 subprocess로 호출하여 실제 동작 검증
- Checkpoints에서 모든 테스트 통과를 확인하고 사용자 피드백 수렴
