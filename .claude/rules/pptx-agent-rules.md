---
paths:
  - "modules/pptx/**"
  - "results/pptx/**"
---

# PPTX 에이전트 행동 주의사항

과거 세션에서 반복된 실수 패턴 — 이 항목을 위반하면 즉시 사용자에게 보고한다.

1. **세션 시작 시 CLAUDE.md/모듈 SKILL.md 반드시 읽기** — 읽지 않고 작업 시작 금지
2. **MCP 우선 원칙** — 새 콘텐츠(도형/텍스트박스/이미지) 추가는 MCP 도구만 사용. Python으로 직접 생성 금지 (예: `add_shape()`, `add_textbox()`, `add_picture()`, `prs.save()`)
3. **Executor/Reviewer는 step 정보만 수신** — 전체 Sprint_Contract 전달 금지 (context 낭비 + isolation 위반)
4. **복원 전 버전 확인** — git restore/checkout 전 반드시 커밋 해시와 타임스탬프 확인 후 사용자 승인 받기
5. **단계별 완료 보고 + 토큰 출력** — Planner/각 Executor/각 Reviewer 완료 시 "✅ [역할] STEP N input: N, output: N tokens" 형식으로 즉시 보고. 파이프라인 최종 완료 시 단계별 합산 테이블 출력
6. **병렬→순차 전환 금지** — 병렬 실행이 합의된 상태에서 사용자 동의 없이 순차로 변경 금지
7. **MCP 불가 항목 즉시 보고** — MCP로 구현 불가능한 항목 발견 시 즉시 중단하고 대안 제시 (무단 대체 금지)
8. **python-pptx 허용 범위** — `modules/pptx/utils/` 내 지정된 유틸만 사용. 새 shape 생성 용도로 쓰면 위반
