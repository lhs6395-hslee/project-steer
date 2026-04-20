# 비활성화 레이아웃 목록

> 아래 레이아웃은 현재 디자인 전면 교체가 필요하여 비활성화 상태입니다.
> 프리젠테이션 생성 파이프라인(planner/executor)에서 **슬라이드 타입 선택 시 제외**하세요.

## 비활성화 레이아웃

| 레이아웃 | 슬라이드 ID | 현 파일 idx | 비활성화 이유 |
|---------|------------|------------|-------------|
| L27 Pyramid Hierarchy | `pyramid_hierarchy` | 28 | 디자인 미완성 — 전면 재설계 필요 |
| L30 Cycle Loop | `cycle_loop` | 31 | 디자인 미완성 — 전면 재설계 필요 |
| L31 Venn Diagram | `venn_diagram` | 32 | 디자인 미완성 — 전면 재설계 필요 |
| L32 Center Radial | `center_radial` | 33 | 디자인 미완성 — 전면 재설계 필요 |
| L33 Fishbone | `fishbone_cause_effect` | 34 | 디자인 미완성 — 전면 재설계 필요 |
| L34 Infinity Loop | `infinity_loop` | 35 | 디자인 미완성 — 전면 재설계 필요 |
| L35 Speedometer Gauge | `speedometer_gauge` | 36 | 디자인 미완성 — 전면 재설계 필요 |
| L36 Mind Map | `mind_map` | 37 | 디자인 미완성 — 전면 재설계 필요 |

## Planner 지시문

```
[비활성화 레이아웃 제외 규칙]
슬라이드 타입 선택 시 아래 레이아웃은 사용하지 않는다:
pyramid_hierarchy (L27), cycle_loop (L30), venn_diagram (L31),
center_radial (L32), fishbone_cause_effect (L33), infinity_loop (L34),
speedometer_gauge (L35), mind_map (L36)
```

## 재활성화 조건

- 디자인 전면 교체 완료 (새 PPTX 템플릿 기준으로 슬라이드 재생성)
- layout-spec.md 해당 섹션 `⛔ [비활성화]` 태그 제거
- 이 파일에서 해당 행 삭제

## 활성화 레이아웃 범위

L01~L26 (단, L28 Org Chart, L29 Temple Pillars 포함)

| 카테고리 | 활성 레이아웃 |
|---------|------------|
| 카드 | L01~L05 |
| 타임라인 | L06~L08 |
| 비교 | L09~L13 |
| 분석 | L14~L16 |
| 이미지 | L17~L19 |
| 리스트 | L20~L22 |
| KPI/통계 | L23~L24 |
| 구조 | L25~L26, L28, L29 |
