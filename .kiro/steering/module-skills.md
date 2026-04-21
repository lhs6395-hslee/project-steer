---
inclusion: fileMatch
fileMatchPattern: "modules/**/*"
---

# 모듈별 도메인 스킬 가이드

모듈 작업 시 해당 모듈의 `SKILL.md`를 참조하세요.

## 모듈 목록

| 모듈 | 경로 | 용도 |
|------|------|------|
| pptx | `modules/pptx/SKILL.md` | 프레젠테이션 생성 |
| docx | `modules/docx/SKILL.md` | 문서 생성 |
| wbs | `modules/wbs/SKILL.md` | 작업 분해 구조 |
| trello | `modules/trello/SKILL.md` | 보드/카드 관리 |
| dooray | `modules/dooray/SKILL.md` | 태스크/마일스톤 관리 |
| google_workspace | `modules/google_workspace/SKILL.md` | 파일/폴더 관리 |
| datadog | `modules/datadog/SKILL.md` | 모니터링/대시보드 |

## 규칙

- 모듈 작업 시 반드시 해당 SKILL.md의 체크리스트 기준으로 검증
- 모듈 간 의존성이 있으면 Orchestrator 스킬 참조
- 새 모듈 추가 시 동일한 SKILL.md 구조를 따를 것
