# Module-Specific Review Checklists

Each module has a tailored checklist that the Reviewer uses for evaluation.
The Orchestrator loads the appropriate checklist based on the target module.

## pptx (Presentation)

| Criterion | Description |
|-----------|-------------|
| completeness | All requested slides are present |
| slide_structure | Logical flow: title → content → conclusion |
| content_accuracy | Data and text are factually correct |
| visual_consistency | Fonts, colors, layouts are uniform |
| template_compliance | Follows the designated template |
| text_overflow | 텍스트가 텍스트박스를 넘지 않는지 검증. 표지 제목(50pt)과 본문 제목(28pt)은 멀티라인 허용(최대 3줄) — 줄 수 ≤ 3이고 필요 높이 ≤ 텍스트박스 높이이면 PASS. 목차 섹션명(24pt)은 1줄 기준. 높이 검증: 줄 수 × font_size × 1.2 ≤ 텍스트박스 높이. |
| format_preservation | 표지/목차/끝맺음 등 템플릿 shape 텍스트 교체 시 원본 서식(scheme color, 폰트명, 크기) 보존 여부 검증. tf.clear() 사용 금지 규칙 준수 확인. |
| design_quality | 디자인 품질 종합 평가. 가시성(텍스트 크기/대비/여백이 읽기 쉬운가), 심미성(레이아웃 균형, 색상 조화, 요소 정렬이 깔끔한가), 전문성(대상 청중에게 신뢰감을 주는 수준인가). 평가 기준: (1) 텍스트-배경 대비 — 밝은 배경에 어두운 텍스트, 어두운 배경에 밝은 텍스트 (2) 여백 균형 — 콘텐츠가 한쪽으로 치우치지 않고 좌우/상하 균등 (3) 요소 정렬 — 같은 역할의 shape들이 수평/수직 정렬 (4) 정보 밀도 — 슬라이드당 핵심 메시지 1~2개, 텍스트 과밀 금지 (5) 시각적 계층 — 제목>부제>본문 크기/굵기 차이로 정보 우선순위 명확 (6) 색상 절제 — PRIMARY + 1~2개 보조색만 사용, 무지개 금지 |

## docx (Document)

| Criterion | Description |
|-----------|-------------|
| completeness | All required sections are present |
| formatting | Headings, lists, tables are properly formatted |
| content_accuracy | Information is correct and up-to-date |
| section_structure | Logical document flow |
| style_compliance | Follows style guide |

## wbs (Work Breakdown Structure)

| Criterion | Description |
|-----------|-------------|
| completeness | All project scope is covered |
| task_hierarchy | Proper parent-child decomposition |
| dependency_validity | Dependencies form a valid DAG |
| estimation_reasonableness | Effort estimates are realistic |
| scope_coverage | No scope gaps or overlaps |

## trello (Board Management)

| Criterion | Description |
|-----------|-------------|
| completeness | All tasks are represented as cards |
| board_structure | Lists reflect workflow stages |
| card_detail | Cards have descriptions, labels, due dates |
| label_consistency | Labels are used consistently |
| workflow_logic | Card flow matches process logic |

## dooray (Task Management)

| Criterion | Description |
|-----------|-------------|
| completeness | All tasks are created |
| task_assignment | Tasks are assigned to appropriate members |
| priority_accuracy | Priorities reflect actual urgency |
| milestone_alignment | Tasks align with project milestones |
| notification_setup | Notifications are configured correctly |

## gdrive (File Management)

| Criterion | Description |
|-----------|-------------|
| completeness | All files are uploaded/organized |
| file_organization | Logical folder hierarchy |
| permission_correctness | Sharing permissions are correct |
| naming_convention | Files follow naming standards |
| folder_structure | Folders reflect project structure |

## datadog (Monitoring)

| Criterion | Description |
|-----------|-------------|
| completeness | All required monitors are created |
| metric_accuracy | Correct metrics are being tracked |
| alert_threshold | Thresholds are appropriate |
| dashboard_clarity | Dashboards are readable and useful |
| query_correctness | Datadog queries return expected data |
