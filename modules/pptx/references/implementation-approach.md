# PPTX 레이아웃 구현 방식 변천사

작성일: 2026-04-20  
대상: L01~L36 구현 방식 및 선택 근거

---

## L01~L12: 파이프라인 방식 (정석)

### 실행 구조

```
Orchestrator
  └─ @planner  → Sprint_Contract JSON 생성
       └─ @executor (병렬)  → MCP pptx 도구로 슬라이드 생성
            └─ @reviewer (병렬)  → 적대적 검증 (acceptance_criteria 기준)
```

### 구체적 흐름

1. **Planner** — layout-spec.md + design-spec.md 읽어 Sprint_Contract JSON 생성
   - 각 step에 `action`, `acceptance_criteria`, `constraints` 정의
   - `dependency` 수준으로 병렬/순차 실행 순서 결정

2. **Executor** — MCP pptx 도구만 사용하여 슬라이드 생성
   - `mcp__pptx__open_presentation` → `mcp__pptx__add_slide` → `mcp__pptx__add_shape` → `mcp__pptx__save_presentation`
   - python-pptx 직접 사용 금지 (pptx-agent-rules.md #2)

3. **Reviewer** — Executor 결과물을 독립적으로 검증
   - Information isolation: Executor reasoning 접근 불가
   - `verdict.schema.json` 기준으로 PASS/FAIL 판정
   - FAIL 시 재시도 (최대 5회)

### 토큰 소비

| 단계 | 특징 | 토큰 규모 |
|------|------|---------|
| 초기 (L01~L08) | 최적화 전 | ~449K/슬라이드 (MISTAKES.md #26) |
| 개선 후 (L09~L12) | step isolation 적용 | ~80K~150K/슬라이드 |

### 장점

- **표준화**: MCP 도구 체인으로 일관된 품질
- **자동 검증**: Reviewer가 acceptance_criteria 기준으로 독립 검증
- **재현 가능**: Sprint_Contract JSON으로 재실행 가능
- **information isolation**: Executor ↔ Reviewer 간 결과 격리

### 단점

- **토큰 비용 높음**: Planner + 복수 Executor + Reviewer 전체 소비
- **속도 느림**: 파이프라인 3단계를 순차/병렬 처리
- **단순 작업에 과잉**: 1개 슬라이드에 3단계 파이프라인은 낭비

---

## L13~: 직접 실행 방식 (변경)

### 실행 구조

```
Orchestrator (직접)
  └─ Read layout-spec.md (해당 L# 섹션)
  └─ Read design-spec.md (색상/폰트/WCAG 기준)
  └─ python-pptx Bash 직접 실행
  └─ 수동 검증 (슬라이드 텍스트/shape 수 확인)
```

### 선택 이유

#### 1. CLAUDE.md "단순 작업 → 직접 실행 허용" 조건 충족

```
단순 작업 → 직접 실행 허용:
- 슬라이드 1~2개 추가 (스펙 명확한 L01~L15)
- python-pptx 또는 utils/ 유틸리티만 사용
```

L13~L15는 슬라이드 1개씩, layout-spec.md에 EMU 좌표까지 완전히 명세된 상태.

#### 2. 스펙 완성도

L13~L15는 layout-spec.md에 다음이 모두 명시됨:

| 항목 | 내용 |
|------|------|
| EMU 좌표 | 모든 shape의 left/top/width/height |
| 색상 | RGB 값 + WCAG 대비율 사전 검증 완료 |
| 폰트 | 요소별 폰트명/크기/bold/color 확정 |
| 구조 | Pros/Cons/Verdict 바 배치 도식 포함 |
| 데이터 구조 | `data = {}` python dict 예시 포함 |

Planner가 추론해야 할 불확실성이 없으므로 파이프라인 불필요.

#### 3. 비용 비교

| 모델 | 파이프라인 1슬라이드 추정 비용 | 직접 실행 추정 비용 |
|------|------------------------------|-------------------|
| Claude Opus 4.6 | ~$2.44 | ~$0.07 |
| Claude Sonnet 4.6 | ~$1.46 | ~$0.12 |
| Claude Haiku 4.5 | ~$0.49 | ~$0.02 |

직접 실행 시 약 **10~20배 비용 절감**.

#### 4. 검증 간소화

layout-spec.md L13~L15 섹션에 WCAG 대비율이 사전 검증 완료 상태:

```
| SUB_GREEN #B2D9CD | DARK_GRAY #212121 | 8.5:1 | ✅ AAA | L13 Pros |
| SUB_ORANGE #F6C0A8 | DARK_GRAY #212121 | 7.2:1 | ✅ AA | L13 Cons |
| PRIMARY #0043DA | 흰색 #FFFFFF | 7.2:1 | ✅ AA | Verdict 바 |
```

Reviewer의 색상 검증 단계가 스펙 단계에서 이미 완료.

### 실제 구현 시 발생한 이슈 (교훈)

#### 이슈 1: Haiku 모델 정확도 부족

- **증상**: margin=0을 중제목뿐 아니라 본문제목까지 적용, 상단 placeholder 전체 제거
- **원인**: Haiku 4.5의 컨텍스트 처리 능력 한계 — 스펙 세부사항 누락
- **조치**: Sonnet 4.6으로 전환 후 재구현

**margin=0 규칙 (명확화):**

| 요소 | margin=0 적용 | 이유 |
|------|-------------|------|
| 중제목 TextBox (20pt) | **필수** | 레이아웃 좌표와 정확히 맞춰야 함 |
| 중제목 설명글 TextBox (12pt) | **필수** | 동일 |
| 본문제목 TextBox (16pt) | **불필요** | 독립 배치, 기본 margin으로 가독성 충분 |
| 본문설명 TextBox (13pt) | **불필요** | 동일 |
| 패널 내 TextBox | **불필요** | 패널 내부 여백이 기본 margin 역할 |

#### 이슈 2: 상단 bar placeholder 누락

- **증상**: `for ph in list(slide.placeholders): ph.element.getparent().remove(ph.element)` — 모든 placeholder 일괄 제거
- **원인**: 레이아웃 1(본문)의 placeholder가 상단 바임을 인식하지 못함
- **조치**: placeholder 제거 코드 삭제. 레이아웃 상속 placeholder는 수정 없이 유지.

**상단 bar placeholder 위치:**

```
| placeholder 상단바 | left=354806 | top=101016 | width=2807494 | height=250530 |
```

수정 불필요 — `add_slide(layout)` 시 자동 상속됨.

#### 이슈 3: 슬라이드 위치 삽입

- **증상**: `prs.slides.add_slide()` → 항상 맨 뒤에 추가됨
- **조치**: `modules/pptx/utils/reorder_slides.py`의 `move_slide()` 사용

```python
from modules.pptx.utils.reorder_slides import move_slide
slide = prs.slides.add_slide(layout)  # 맨 뒤 추가
move_slide(prs, len(prs.slides)-1, target_idx)  # 목표 위치로 이동
```

---

## 방식 선택 기준 (요약)

| 조건 | 권장 방식 |
|------|---------|
| 슬라이드 3개 이상 | 파이프라인 (Planner→Executor→Reviewer) |
| L09~L36 복잡 레이아웃 조합 | 파이프라인 |
| 데이터 검증 필요 (외부 API 등) | 파이프라인 |
| 슬라이드 1~2개, 스펙 명확 (L01~L15) | **직접 실행** |
| 텍스트/색상/폰트 수정 (좌표 변경 없음) | **직접 실행** |
| 슬라이드 순서 변경, 삭제, 병합 | **직접 실행** |

---

## 적용 현황

| 범위 | 방식 | 상태 |
|------|------|------|
| L01~L12 | 파이프라인 (MCP Executor) | ✅ 완료 |
| L13 Pros & Cons | 직접 실행 (python-pptx) | ✅ 완료 |
| L14 Do / Don't | 직접 실행 예정 | 📋 대기 |
| L15 SWOT Matrix | 직접 실행 예정 | 📋 대기 |
| L16~L36 | 방식 미결정 (스펙 완료) | 📋 대기 |
