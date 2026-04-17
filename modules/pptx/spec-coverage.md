# PPTX 모듈 스펙 커버리지 — ai-agent-engineering-spec-2026.md

분석 기준일: 2026-04-18 | 스펙 버전: v1.1 (36개 요구사항)

---

## 전체 현황

| 상태 | 개수 | 비율 |
|------|------|------|
| ✅ 완전 구현 | 9개 | 25% |
| ⚠️ 부분 구현 | 17개 | 47% |
| ❌ 미구현 | 10개 | 28% |

---

## ✅ 완전 구현 (9개)

### 요구사항 1 — Orchestrator 프로세스 구현
**구현 방식:** 이 Claude 세션 자체가 Orchestrator 역할 수행
- `pipeline-orchestration.md` 규칙에 따라 planner → executor → reviewer 순서 조율
- recon step 자동 분기 (Create/Modify 모드 판별 후 executor spawn)
- 실패 step만 재시도, approved step 스킵

### 요구사항 2 — Planner 에이전트 구현
**구현 방식:** `.claude/agents/planner.md`
- Claude opus 모델로 독립 subagent 실행
- Sprint_Contract JSON 단독 출력 (도구 사용 금지, maxTurns=3)
- PPTX 전용 패턴 A(Create)/B(Modify) 명시 — step별 독립 생성, merge step 구조
- 슬라이드별 target_slide_index, acceptance_criteria, constraints 분리 작성 강제

### 요구사항 5 — Guardian 에이전트 구현
**구현 방식:** `scripts/agents/guardian.sh` + `.claude/settings.json` PreToolUse hook
- 정규식 Pattern_Matcher로 위험 명령 탐지 (Claude API 호출 없음)
- exit code 2(차단) / exit code 0(허용)
- 차단 대상: rm -rf, DROP TABLE, git push --force 등
- MCP 도구 경로 외 pptx 직접 접근 차단

### 요구사항 6 — 파일 기반 에이전트 간 통신
**구현 방식:** `.pipeline/{RUN_ID}/` 폴더 구조
- `schemas/handoff_file.schema.json`: id, timestamp, from_agent, to_agent, status, payload 완비
- `sprint_contract.json`, `verdict_N.json` 파일로 에이전트 간 상태 전달
- 파이프라인 실행 중 불변 유지 (완료 후 아카이브 허용)

### 요구사항 7 — 독립 Agent_Session 관리
**구현 방식:** subagent 정의 파일별 독립 모델 + mcpServers inline
- planner(opus), executor(sonnet), reviewer(sonnet) 각각 독립 세션
- mcpServers inline 정의로 subagent 시작 시 MCP 연결, 종료 시 해제
- 에이전트 간 대화 이력 공유 없음 (컨텍스트 격리)

### 요구사항 11 — Sprint_Contract 스키마 정의
**구현 방식:** `schemas/sprint_contract.schema.json`
- task, module, mode(create/modify), steps, acceptance_criteria, constraints, risks 필드 완비
- steps 배열: id, action, dependencies, target_slide_index, acceptance_criteria, estimated_complexity, constraints
- DAG 의존성 검증, PPTX 패턴 A/B 분기 명시

### 요구사항 12 — Verdict 스키마 정의
**구현 방식:** `schemas/verdict.schema.json`
- verdict(approved/rejected/partial), score(0-100), iteration 필드
- checklist_results 배열: item, status(pass/fail/warn), actual_value, expected_value
- constraint_violations, issues, suggestions 배열
- code_location 대신 EMU 수치/shape index 기반 위치 명시

### 요구사항 32 — CLAUDE.md 운영 원칙 준수
**구현 방식:** `CLAUDE.md` (~53줄)
- 60줄 이하 유지 중
- 상세 내용은 `@.claude/docs/pipeline-orchestration.md` 참조 분리
- 금지 규칙(백업 파일 자동 생성 금지 등)과 강제 규칙(파이프라인 필수) 명확 구분

### 요구사항 33 — 멀티 에이전트 패턴 선택 기준 (부분 해당)
**구현 방식:** GAN-Style + Parallel + Orchestrator 3가지 패턴 구현
- GAN-Style: executor(Generator)와 reviewer(Evaluator) 적대적 검증
- Parallel: 슬라이드별 executor subagent 동시 spawn
- Orchestrator: 이 Claude 세션이 전체 워크플로우 조율

---

## ⚠️ 부분 구현 (17개)

### 요구사항 3 — Generator(Executor) 에이전트
**구현됨:** `.claude/agents/executor.md` MCP+python-pptx 하이브리드, step별 독립 실행, /tmp/slide_N.pptx 저장 패턴, MCP 우선 원칙 표  
**미구현:** fail Verdict 수신 후 executor 자체 재시도 로직 없음 (Orchestrator에만 의존), Feedback_Loop 최대 횟수 executor.md 미명시

### 요구사항 4 — Evaluator(Reviewer) 에이전트
**구현됨:** python-pptx 직접 검증, information isolation 명시, EMU 수치·shape 좌표 직접 측정, constraint_violations 체크리스트  
**미구현:** tsc/eslint/보안 스캐너 통합 없음, few-shot 보정(관대한 평가 편향 방지 예시) 없음, 코드 생성 전 acceptance_criteria 사전 협상 단계 없음

### 요구사항 8 — Feedback_Loop
**구현됨:** `pipeline-orchestration.md`에 max 5회 재시도 명시, reviewer rejected → executor 재spawn  
**미구현:** Confidence_Trigger 기반 동적 횟수 조정 없음 (항상 5회 고정), 반복 횟수를 Handoff_File에 기록하는 로직 없음

### 요구사항 9 — IDE Hooks 마이그레이션
**구현됨:** guardian.sh가 PreToolUse hook으로 runCommand 개념 구현, kairos.sh PostToolUse hook 연결, MCP 도구로 askAgent 방식 사실상 대체  
**미구현:** Dispatcher 패턴(동일 이벤트 여러 훅 순차 실행) 없음, 훅별 exit code 0/1/2 체계 일관 적용 미확인

### 요구사항 10 — 에이전트 실행 스크립트
**구현됨:** guardian.sh, kairos.sh, sync_pipeline.sh 존재  
**미구현:** planner/executor/reviewer 독립 실행 .sh 스크립트 없음 (@-mention subagent로 대체), 입력 Handoff_File 경로를 명령줄 인자로 받는 구조 없음

### 요구사항 14 — 비용 및 토큰 관리
**구현됨:** 파이프라인 완료 시 토큰 집계 + 비용 환산 테이블 출력, Vertex AI On-demand 가격 기준 명시  
**미구현:** 토큰 예산 상한 설정 파일 없음, 예산 80% 경고·초과 시 파이프라인 중단 메커니즘 없음

### 요구사항 15 — IDE 어댑터 패턴
**구현됨:** Claude Code → Kiro 단방향 sync 원칙 문서화, sync_pipeline.sh 존재  
**미구현:** IDE 자동 감지 로직 없음, ide_adapters 설정 섹션 없음, Antigravity/VS Code 변환 없음

### 요구사항 16 — IDE 간 Sync 파이프라인
**구현됨:** sync_pipeline.sh 존재, Claude Code → Kiro 단방향 원칙 명시  
**미구현:** 구체적 변환 규칙 스크립트 미작성, 충돌 감지·diff 기록 없음, Antigravity/VS Code 변환 없음

### 요구사항 19 — KAIROS 상시 감시 모드
**구현됨:** kairos.sh 존재, PostToolUse hook 연결, Evaluator와 역할 분리 개념 문서화  
**미구현:** fs.watch 기반 실시간 파일 변경 감지 구현 여부 불명확, CPU 5% 이하·디바운싱(500ms) 적용 여부 미확인

### 요구사항 24 — 에이전트 루프 4단계
**구현됨:** Take Action(executor) + Verify Work(reviewer) 2단계 명확히 분리, step별 독립 subagent로 Context_Reset 암시적 적용  
**미구현:** Gather Context / Repeat 단계 명시적 정의 없음, step별 Context_Reset 전략 문서화 없음

### 요구사항 25 — 하네스 6대 구성요소
**구현됨:** 컨텍스트 엔지니어링(CLAUDE.md), 도구 오케스트레이션(MCP 우선 원칙), 검증 루프(reviewer), 오류 복구(max 5회 재시도)  
**미구현:** 상태·메모리(Auto_Dream 없음), 인간 개입 제어(Confidence_Trigger 없어 자동화 수준 고정)

### 요구사항 26 — Context Engineering — 실패 모드 방지
**구현됨:** Distraction 방지(step 정보만 수신, 전체 Sprint_Contract 전달 금지), Poisoning 방지(guardian.sh 입력 검증), Confusion 방지(CLAUDE.md + step별 constraints 계층 분리)  
**미구현:** Clash 방지(동일 파일 동시 수정 차단 로직 없음), Context_Failure_Mode 탐지·회피 전략 없음

### 요구사항 27 — Context Rot 방지
**구현됨:** step별 독립 subagent 실행으로 세션 간 컨텍스트 공유 없음 (암시적 적용)  
**미구현:** 50,000 토큰 임계값 명시 없음, Context_Rot 경고 Verdict 기록 없음, 임계값 초과 시 자동 트리거 없음

### 요구사항 28 — 에이전트 실패 패턴 방지
**구현됨:** 불명확한 요구사항 방지(acceptance_criteria 스키마 강제), 검증 없는 자동수락 방지(reviewer 필수), 긴 세션 드리프트 방지(step별 새 subagent)  
**미구현:** 권한 과다 방지(step 단위 도구 권한 제한 없음, executor가 모든 MCP 도구 접근 가능), 컨텍스트 과부하 50k 임계값 자동 적용 없음

### 요구사항 29 — Right Altitude 원칙
**구현됨:** planner.md constraints 작성 규칙("해당 step에 직접 관련된 것만"), CLAUDE.md 규칙 "원칙 + 이유" 형식 부분 적용  
**미구현:** "원칙 1줄 + 이유 1줄 + 예시 1-2개" 형식이 모든 constraints에 일관 적용 안 됨

### 요구사항 31 — Ralph Loop 방지
**구현됨:** planner.md "Output ONLY JSON" 명시(순환 참조 차단), executor.md/reviewer.md maxTurns 설정  
**미구현:** 동일 파일 3회 연속 읽기 패턴 감지 로직 없음, Ralph_Loop 감지 시 롤백 없음

### 요구사항 36 — 에이전트 엔지니어링 진화 단계
**구현됨:** 실질적으로 2-3단계(Context Engineering + Harness Engineering) 혼재 운영  
**미구현:** 성숙도 단계를 metrics/maturity.json에 기록·모니터링하는 메커니즘 없음

---

## ❌ 미구현 (10개)

| 요구사항 | 이유 / 영향 |
|---------|-----------|
| 13. Confidence_Trigger | 단순 수정도 항상 풀 파이프라인 강제. 연쇄 미구현: 20(UltraPlan), 30(Plan-Critic-Build) |
| 17. Git Worktree | /tmp로 대체 중. 멀티 모듈 병렬 확장 시 필요 |
| 18. Auto-Dream | 스키마에 정의됐으나 스크립트 없음. `.pipeline/` 폴더 이미 누적 중 |
| 20. UltraPlan | Confidence_Trigger 없어 연쇄 미구현. `.pipeline/plans/` 공 상태 |
| 21. SDD | 고정 레이아웃 기반. requirements.md 자동 추출 없음 |
| 22. Agent Team | Coordinator 없음. 멀티 모듈 병렬 협업 불가 |
| 23. Harness Subtraction | metrics/ 공 상태. 컴포넌트 기여도 데이터 없음 |
| 30. Plan-Critic-Build | Critic 에이전트 없음. Sprint_Contract 오류가 executor에서야 발견됨 |
| 34. 신뢰성 수학 | 성공률 측정 없음. 파이프라인 신뢰성 수치 없음 |
| 35. SDD + TDD | TDD 워크플로우 미적용. acceptance_criteria는 있으나 사전 테스트 작성 없음 |

---

## 개선 우선순위

| 우선순위 | 과제 | 근거 |
|---------|------|------|
| 즉시 | Auto-Dream 스크립트 작성 (요구사항 18) | `.pipeline/` 폴더 이미 누적 중 |
| 즉시 | metrics/ 기본 성공률 기록 (요구사항 34 일부) | 파이프라인 신뢰성 가시화 |
| 중기 | Plan-Critic-Build Critic 에이전트 (요구사항 30) | Sprint_Contract 품질 조기 검수 |
| 중기 | Confidence_Trigger 최소 구현 (요구사항 13) | 단순 수정 시 파이프라인 단축 |
| 장기 | Git Worktree 실제 사용 (요구사항 17) | 멀티 모듈 병렬 작업 시 |
| 장기 | Agent Team Coordinator (요구사항 22) | pptx+docx+dooray 복합 작업 시 |

---

*분석 기준일: 2026-04-18 | 스펙: specs/ai-agent-engineering-spec-2026.md v1.1*
