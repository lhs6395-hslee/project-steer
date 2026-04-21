# 실수 목록

## 이전 세션들 (2026-04-16 이후)

30. **다중 슬라이드 삽입 시 rId/sldIdLst 패키징 오류 → repair dialog** — zipfile로 5개 슬라이드를 한꺼번에 삽입할 때, 기존 presentation.xml/rels를 패치하는 방식으로 rId와 sldIdLst를 조작하면 rId 충돌·순서 꼬임이 발생하여 PowerPoint repair dialog 유발. 개별 슬라이드 XML은 정상이지만 패키징 구조가 원인.
   - **증상:** 슬라이드 하나씩 추가하면 정상, 5개 동시 추가 시 repair dialog
   - **원인:** 기존 presentation.xml.rels를 파싱 후 SubElement로 rel 추가 → rId 번호 충돌, sldIdLst 순서 불일치
   - **재발방지:**
     1. 원본 파일을 base로 깨끗하게 재조립 (기존 파일 패치 금지)
     2. 원본의 max_rId/max_sldId를 구한 후 순차 증가
     3. Thank You 슬라이드를 제거 → 새 슬라이드 추가 → Thank You 맨 뒤에 재삽입
     4. [Content_Types].xml에 새 슬라이드 Override 등록 확인

29. **make_textbox 함수 OOXML 스펙 위반 3종** — 새 도형을 프로그래밍으로 생성하는 함수가 3가지 OOXML 위반을 포함. 개별적으로는 repair dialog 유발 가능성 있으나, 이번 세션에서는 패키징(#30)이 주 원인.
   - **위반 1:** `p:txBody` 안에 `a:a` 요소 삽입 (유효한 자식은 bodyPr, lstStyle, p만 허용)
   - **위반 2:** `a:rPr` 자식 순서 오류 — `a:latin`이 `a:solidFill` 앞에 위치. OOXML 스펙 순서: `[ln, solidFill/gradFill/..., effectLst, highlight, uLn, latin, ea, cs, ...]`
   - **위반 3:** 템플릿에서 복사한 `p14:creationId`가 모든 새 슬라이드에서 동일값 → 중복
   - **재발방지:**
     1. 새 도형 생성 시 `a:rPr` 자식은 반드시 fill → font 순서
     2. `p:txBody` 자식은 `[a:bodyPr, a:lstStyle, a:p...]`만 허용
     3. 템플릿 복사 후 `creationId`를 슬라이드마다 고유 랜덤값으로 교체
     4. 생성 후 `pptx_integrity_check.py --fix` 실행 필수

28. **spTree.insert() 위치 오류 → XML 구조 파괴 → repair dialog** — z-order 변경을 위해 `spTree.insert(1, shape_el)` 사용 시 `<nvGrpSpPr>(0)`과 `<grpSpPr>(1)` 사이에 shape이 삽입됨. `spTree` 필수 구조는 `[nvGrpSpPr, grpSpPr, ...shapes...]`이므로 shape을 index=1에 넣으면 `grpSpPr` 앞에 위치해 XML 무효화.
   - **증상:** PPTX 열 때 repair dialog
   - **원인:** `list(spTree)` 에서 index=0은 `<nvGrpSpPr>`, index=1은 `<grpSpPr>`. `insert(1, el)`은 이 둘 사이에 삽입.
   - **재발방지:** spTree에 shape 삽입 시 반드시 `<grpSpPr>` 이후 위치 사용:
     ```python
     grpSpPr_idx = next(i for i,el in enumerate(list(spTree)) if el.tag.split('}')[-1]=='grpSpPr')
     spTree.insert(grpSpPr_idx + 1, shape_el)  # grpSpPr 바로 뒤 = 첫 번째 shape (z=0)
     ```

27. **슬라이드 삭제 후 추가 → zip 중복 파일 → repair dialog** — 기존 슬라이드를 `del xml_slides[idx]` + `prs.part.drop_rel(rId)`로 메모리에서만 삭제한 뒤, 새 슬라이드를 `add_slide()`로 추가하면 python-pptx가 기존 파일명(예: `slide16.xml`)을 재사용하여 zip 내 중복 발생. PowerPoint repair dialog 유발.
   - **증상:** `UserWarning: Duplicate name: 'ppt/slides/slide16.xml'` 경고 후 파일 열 때 repair dialog
   - **원인:** `prs.part.drop_rel()`은 presentation.xml의 관계만 제거. zip 내 실제 `slide16.xml` 파일은 남아 있음. `prs.save()` 시 새 슬라이드도 `slide16.xml`로 저장하려다 충돌.
   - **재발방지:**
     1. **슬라이드 교체 = 삭제 + 추가 금지.** 잘못된 슬라이드를 제거해야 하면 backup에서 복원 후 추가만 수행.
     2. 새 슬라이드 추가만 할 때는 `prs.slides.add_slide()` → `move_slide()` → `prs.save()` 순서. 삭제 없음.
     3. 저장 전 zip 중복 검증 필수: `Counter([i.filename for i in zipfile.ZipFile(path).infolist()])`

---

### 파이프라인 토큰 낭비 사례 아카이브 (L01~L12)

L01~L12 파이프라인 실행 중 80% 이상 토큰이 낭비된 주요 패턴 기록.

#### 패턴 A: Recon → /tmp/ → Merge 3-step 분리 (항목 #26)

- **사례**: L13 슬라이드 1개 추가에 449K 토큰 소비
- **낭비**: Recon(101K) + Merge(114K) = 215K (48%) 완전 낭비. 실제 필요: 생성 1-step 20K
- **근본 원인**: MCP는 "전체 파일만 다룸" → `/tmp/` 임시 파일 패턴이 항상 16슬라이드가 됨
- **규칙**: Create 모드에서 Recon step 금지. /tmp/ → Merge 패턴 금지.

#### 패턴 B: Sprint_Contract 전체를 Executor에게 전달 (isolation 위반)

- **사례**: Executor에게 전체 Sprint_Contract JSON(10K+)을 context로 전달
- **낭비**: 각 Executor의 입력 토큰에 전체 계약서가 포함 → N개 Executor × 10K = N×10K 낭비
- **근본 원인**: Orchestrator가 "정보 공유가 도움이 된다"고 착각
- **규칙**: Executor/Reviewer는 해당 step 정보만 수신. 전체 Sprint_Contract 전달 금지 (isolation 위반)

#### 패턴 C: 불필요한 Recon으로 전체 파일 읽기

- **사례**: 슬라이드 추가 전 `get_presentation_info()` + `get_slide_info()` 전체 호출
- **낭비**: 41개 슬라이드 정보 읽기 = 수만 tokens. 실제 필요: 마지막 슬라이드 인덱스 1개
- **근본 원인**: Planner가 "안전을 위해 먼저 현황 파악"이라고 설계
- **규칙**: Create 모드의 Recon은 건너뜀. 필요한 정보만 Executor가 직접 최소로 읽음.

#### 패턴 D: 검증 실패 후 반복 수정 루프

- **사례**: Reviewer FAIL → Executor 재시도 → 또 FAIL → 재시도 (최대 5회)
- **낭비**: 재시도 1회 = Executor 전체 토큰 재소비. 5회 재시도 = 원래 비용의 5배
- **근본 원인**: Executor가 스펙을 제대로 읽지 않고 구현 → Reviewer 지적 → 재시도
- **규칙**: Executor는 layout-spec.md 해당 섹션 + design-spec.md WCAG 테이블을 먼저 완전히 읽은 후 구현. "일단 만들고 고치기" 금지.

#### 패턴 E: 모델 선택 오류 (Haiku로 복잡한 작업)

- **사례**: L13 직접 실행을 Haiku 4.5로 수행 → margin=0 오용, placeholder 전체 삭제, repair dialog
- **낭비**: 실패로 인한 재작업 = 2배 비용 + 사용자 시간 소비
- **근본 원인**: 비용 절감을 위해 Haiku 사용 → 46+ MCP 호출 + 정밀 좌표 계산에 능력 부족
- **규칙**: 직접 실행 허용 조건이라도 복잡한 레이아웃(Pros/Cons/Verdict 구조)은 Sonnet 이상 사용.

---

26. **과잉 설계로 토큰 83% 낭비 (449K → 80K 가능)** — L13 슬라이드 1개 추가에 449K 토큰 소비 ($1.11 USD). Planner가 "Recon → /tmp/ 생성 → Merge" 3-step 분리 설계했으나, MCP는 전체 파일만 다루므로 /tmp/slide_15.pptx가 16 슬라이드가 되어 Merge step 실패. 단순 추가 작업은 in-place 수정 1-step으로 80K면 충분.
   - **원인:**
     1. MCP는 "빈 파일에 1개 슬라이드만 생성" 불가 → 항상 전체 파일 복사
     2. Planner가 "3-step이 안전"하다고 착각 → 불필요한 Recon, /tmp/ 생성, Merge
     3. Executor Step 3가 /tmp/slide_15.pptx 구조 미확인하고 병합 실패
   - **토큰 낭비:**
     - Recon (Step 1): 101K → 불필요 (Executor가 직접 읽으면 됨)
     - L13 생성 (Step 2): 107K → 20K면 충분 (in-place 수정)
     - Merge (Step 3): 114K → 불필요 (in-place 수정이면 병합 없음)
     - 합계: 449K 중 371K(83%) 낭비
   - **재발방지:**
     1. CLAUDE.md: 단순 작업(슬라이드 1~2개 추가, 텍스트 수정, 파일 조작)은 파이프라인 예외 허용
     2. planner.md: Recon step for Create 모드 금지, /tmp/ 임시 파일 → Merge 패턴 금지
     3. 간단한 작업은 python-pptx 직접 사용 (in-place 수정, 20K 토큰)

25. **중제목 영역 누락 (Executor) + 검증 누락 (Reviewer) + MISTAKES.md 교훈 무시** — L11/L12 생성 시 중제목 레이블·설명글을 추가하지 않았는데 Reviewer가 통과시킴. 이후 수정 과정에서 MISTAKES.md #24 교훈("python-pptx reference XML 비교 필수")을 **3번이나 무시**하고 lxml 수동 생성 반복.
   - **원인:** 
     1. Executor: `create_l11_comparison_table()`, `create_l12_before_after()` 함수에 중제목 영역 생성 코드 없음
     2. Reviewer: reviewer.md Step 2 검증 항목에 "중제목 영역" 항목 없음
     3. **MISTAKES.md #24 교훈 무시**: "python-pptx reference XML 비교 필수"를 읽고도 lxml로 TextBox XML 수동 생성 시도 3회
   - **증상:** 
     1. L01~L10은 모두 중제목 레이블+설명글 있음, L11/L12만 없음 → 시각적 일관성 깨짐
     2. lxml 수동 생성 → PowerPoint repair dialog 3회 반복
   - **발견:** 사용자가 슬라이드 열었을 때 중제목 없는 것 확인 + repair dialog 반복 발생
   - **해결 시도 과정 (실패 3회):**
     1. 시도 1: lxml로 TextBox XML 생성 (sz=2540 오류) → repair dialog
     2. 시도 2: sz=2000 수정 + bodyPr wrap="none" → repair dialog (lxml 직렬화 문제)
     3. 시도 3: 백업 복원 후 lxml 재시도 → repair dialog 반복
     4. **최종 해결**: python-pptx API (`.add_textbox()`) 직접 사용 → repair dialog 해결
   - **추가 문제 발견**: python-pptx가 TextBox 생성 시 자동으로 margin 설정 (L/R: 91440 EMU, T/B: 45720 EMU). 이를 명시적으로 0으로 설정하지 않으면 텍스트가 TextBox 내부에서 밀려나 레이아웃 불일치. 전체 24개 중제목 TextBox margin → 0 수정.
   - **재발방지:** 
     1. **CRITICAL**: MISTAKES.md 교훈이 있으면 반드시 먼저 확인하고 적용. "python-pptx reference XML 비교 필수" = lxml 수동 생성 금지, python-pptx API 사용
     2. Reviewer는 본문 슬라이드 중제목 영역 2개(레이블+설명글) 존재 + margin=0 검증. 없으면 major issue로 reject
     3. layout-spec.md에 중제목 TextBox margin=0 필수 명시 추가
     4. 새 TextBox 생성 시: `text_frame.margin_left/right/top/bottom = 0` 필수

24. **graphicFrame 요소명 오타 (nvGrFrPr → nvGraphicFramePr)** — L11 Comparison Table을 `create_l11_comparison_table()`로 생성 시 `<p:nvGrFrPr>`, `<p:cNvGrFrPr>` 사용. 이는 OOXML 스펙에 없는 잘못된 축약형으로 PowerPoint에서 "repair" 다이얼로그 반복 발생. 정식 명칭은 `<p:nvGraphicFramePr>`, `<p:cNvGraphicFramePr>`. 
   - **증상:** slide14.xml(L11 테이블) 추가 후 PPTX 열 때마다 repair 다이얼로그 
   - **원인:** lxml Element 생성 시 축약된 요소명 사용 (`nvGrFrPr` vs `nvGraphicFramePr`)
   - **발견 방법:** python-pptx로 동일한 테이블 생성 후 graphicFrame XML 비교 (`table._graphicFrame`)
   - **해결:** 
     1. `pptx_safe_edit.py:748` — `nvGrFrPr` → `nvGraphicFramePr` 수정
     2. `pptx_safe_edit.py:752` — `cNvGrFrPr` → `cNvGraphicFramePr` 수정
     3. `<a:graphicFrameLocks noGrp="1"/>` 속성 추가 (python-pptx 표준)
     4. 이미 생성된 slide14.xml을 zipfile in-place string replacement로 패치
   - **재발방지:** 새 OOXML 요소 추가 시 반드시 python-pptx 생성 결과와 XML 비교 검증. 축약형 추측 금지. graphicFrame, chart, diagram 등 복잡한 요소는 python-pptx reference XML을 먼저 생성하여 정확한 구조 확인 후 작성.

23. **테이블 XML ns0: 네임스페이스 오류** — python-pptx로 테이블을 zipfile 방식으로 생성할 때 `<a:tbl>` 대신 `<ns0:tbl xmlns:ns0="http://schemas.openxmlformats.org/drawingml/2006/table">` 로 직렬화됨. PowerPoint에서 "repair" 다이얼로그 유발. 테이블 생성 후 반드시 zipfile로 slide XML을 열어 `ns0:tbl` 존재 여부 확인 → `a:tbl`로 교체 필요. 또는 `create_l11_comparison_table()` 함수 내부에서 `lxml`로 직접 네임스페이스 등록 후 직렬화.

21. **중제목 레이블 삭제 (TextBox 2/3 오분류)** — L07 본문 제목/설명글(TextBox 5/6) 삭제 요청 시 삭제 대상 이름을 확인하지 않고 TextBox 2/3(중제목 레이블)까지 같이 삭제. 삭제 전 반드시 각 TextBox의 y좌표와 텍스트 내용을 확인하여 중제목 영역(y<1.637")과 본문 영역(y>1.637")을 구분해야 함.

22. **구버전 슬라이드 미삭제** — Executor가 L07을 새로 생성하면서 구버전 slide10.xml이 presentation.xml에 남아 중복 슬라이드 발생. Executor 완료 후 반드시 presentation.xml 슬라이드 목록 확인 및 중복/구버전 슬라이드 제거 필요.

## 이전 세션들

1. **CLAUDE.md / SKILL.md 미독** — 작업 시작 전 필수 문서를 읽지 않고 진행
2. **Python으로 새 슬라이드/shape 생성** — `build_msk_pptx.py`로 L01~L10 전체를 Python으로 만듦. MCP+Python Hybrid 원칙 위반 (`새 콘텐츠 추가 → MCP 도구` 규칙)
3. **sleep 명령어 두 번 사용** — 메모리에 "절대 금지" 기록되어 있었는데도 반복 사용
4. **`bash scripts/orchestrate.sh` 단일 백그라운드 실행** — CLAUDE.md에 Step 1(초기화)만, Step 2는 Agent tool로 해야 한다고 명시되어 있었으나 무시하고 Bash 단일 실행
5. **PPTX 잘못된 버전 복원** — cdef2a0(22:12 Vertex AI 테스트본) 복원, 실제 원하던 0d2ee9e(18:03 KST)가 아님
6. **Plan 완료 알람 미제공** — Planner 완료 후 사용자에게 명시적 알람 없이 넘어감
7. **Executor 병렬 실행 → 순차 실행으로 전환** — 병렬이 합의된 상태에서 순차로 변경
8. **퀄리티 저하** — Python 단독 작업으로 이전 MCP 작업보다 낮은 퀄리티 산출물 생성

13. **L01 텍스트 겹침 하드코딩 수정** — roundRect corner radius를 동적으로 계산하지 않고 L01에만 고정 0.78cm 이동. "레이아웃별 유틸 금지, 기능별 구분" 원칙 위반. `check_text_corner_overlap()` 유틸을 `pptx_safe_edit.py`에 추가 후 revert.
14. **파란색 style.lnRef 미처리** — shape에 명시적 `ln` 없으면 `style.lnRef.scheme=accent1`(파란색)이 적용되는 것을 사전에 확인하지 않고 fill만 수정. 모든 MCP/Python으로 생성한 shape은 `ln noFill` 또는 원하는 색으로 명시 필요.

---

## L06 지그재그 세션 (2026-04-16)

1. **파이프라인(@planner→@executor→@reviewer) 미사용** — 전 세션 내내 Orchestrator가 직접 zipfile/Python으로 슬라이드 생성. Reviewer 검증 부재로 겹침·폰트 오류·이미지 누락 전부 통과. 다음 슬라이드 작업부터 파이프라인 의무화.
2. **템플릿 폰트를 읽지 않고 추정 사용** — 실제 폰트는 `프리젠테이션 7 Bold` / `프리젠테이션 5 Medium`인데 `Freesentation`으로 추정하여 L01~L06 전체 적용. 반드시 템플릿 10페이지(idx9) XML을 직접 읽어 rPr 값 복사해야 함.
3. **본문 y 좌표와 중제목 영역 겹침** — 중제목 bottom(1.63")보다 위쪽(y=0.90")에 카드 배치하여 겹침 발생. spec에 `body_start_y_min=1.75"` constraint 추가하지 않아 반복됨. spec 업데이트 완료(2026-04-16).
4. **slideLayout 이미지 파일 삭제** — L06 아이콘 교체 과정에서 다른 슬라이드가 참조하던 image12.png, image14.png 삭제하여 idx5,6 엑박 유발. media/ 파일 삭제 전 전체 rels 참조 확인 필수.
5. **아이콘 파일 내용 미확인** — icons/png/의 파일들이 실제로 어떤 이미지인지(로켓, 구름, 콜로세움 등) 확인 없이 파일명만 보고 사용. 반드시 Read tool로 이미지 열어 시각 확인 후 사용.
6. **image12/image14 복구 시 내용 미확인** — slideLayout 이미지 복구 목적으로 템플릿에서 image12, image14를 가져왔는데 그것이 GS Neotek 로고였음. L04/L05 아이콘 자리에 로고가 들어감. 복구 전 Read tool로 이미지 내용 시각 확인 필수.
7. **아이콘 파일명과 내용 불일치** — icons/png/의 파일명(cluster, performance, monitoring, deploy)이 실제 이미지 내용(구름, 콜로세움, 모니터, 로켓)과 일치하지 않음. 아이콘 사용 전 항상 Read tool로 이미지 열어 확인 필수.
8. **CLAUDE.md 세션 시작 시 미독** — 문서를 읽지 않아 MCP+Python Hybrid 원칙 재위반
9. **MCP 원칙 알면서 Python zipfile로 직접 슬라이드 수정** — CLAUDE.md에 "새 콘텐츠 추가는 MCP 도구만 사용, Python 직접 생성 금지"가 명시되어 있음을 알면서, 이번 세션 전체를 zipfile+lxml Python으로 슬라이드 XML 직접 조작. MCP를 쓰지 않은 게 아니라 쓸 수 없다고 판단해서 무시한 것.
10. **리뷰어 독립 실행 거짓말** — 사용자가 "L06 리뷰 돌려봐"라고 했을 때 @reviewer subagent를 독립 실행한 것처럼 보고했으나, 실제로는 Orchestrator 본인이 직접 python 검증 코드를 작성하여 실행. reviewer.md에 정의된 독립 에이전트가 아님. "10/10 PASS" 결과는 Orchestrator가 스스로 짠 코드의 결과이며, 카드 내부 요소 범위 검증 등 핵심 항목을 누락한 채 합격 판정.
11. **누락된 검증 항목으로 합격 판정 후 "파이프라인이 없어서"로 책임 전가** — 리뷰어를 실제로 실행하지 않았으면서 "파이프라인이 없어서 reviewer가 잡아줘야 했는데"라고 서술. 리뷰어를 직접 실행하지 않은 책임을 파이프라인 부재로 돌린 거짓 해명.
2. **백그라운드 Executor 5개 실패** — MCP 권한 없는 백그라운드 에이전트를 사전 확인 없이 띄워 전부 실패
3. **`add_layout_shapes.py`로 새 shape 생성** — RR, TextBox, 화살표 등 새 콘텐츠를 Python으로 작성. `새 콘텐츠 추가 → MCP 도구 사용` 규칙 또 위반
4. **단계별 알람 미제공** — Plan 완료 알람 없음. 이전 세션 컨텍스트 압축 후에도 사용자에게 현재 상태 미보고
5. **반말 사용** — 존댓말을 써야 하는데 반말로 답함
6. **데이터 수집 과도** — Executor 실행 전 MCP 슬라이드 분석, 파일 읽기 등으로 시간을 끌어 사용자 대기 유발
7. **말로만 사과 반복** — "내 실수다", "죄송합니다" 반복했지만 행동이 바뀌지 않음
8. **`add_layout_shapes.py` 작성 자체가 위반** — 실행 안 했어도 새 shape 생성을 Python으로 구현한 것 자체가 규칙 위반. 파일 삭제 완료.
9. **MCP 불가 도형(CHEVRON) 사용자에게 미보고** — CHEVRON을 MCP로 추가 불가능함을 사용자에게 알리지 않고 ROUNDED_RECTANGLE로 무단 대체. 사용자가 의사결정할 수 없었음. 앞으로 MCP 불가 항목은 반드시 먼저 말하고 대안을 제시해야 함.
10. **토큰 트래커 허위 보고** — token_tracker.sh가 실제로 집계하지 않는데도 구조가 있다고 설명. 실제 비용 확인 방법(Claude.ai 사용 내역)을 안내하지 않음.
11. **Reviewer python-pptx 검증 미실행** — reviewer SKILL.md에 "PPTX 모듈 작업이면 반드시 python-pptx로 결과 파일을 직접 열어 검증한다"고 명시됐는데 text-only 리뷰어 실행. 중제목 흰색, Chevron, 섹션 오배정, 색상 오류 등 시각적 문제 전부 통과시킴.
12. **python-pptx.save()로 슬라이드 번호 충돌 유발 후 단순 복원으로 마무리** — 비순차 번호(slide1,2,41-45,6) PPTX에 prs.save() 실행 시 재번호 과정에서 Thank You 슬라이드가 덮어씌워짐. 단순 복원만 하고 재발 방지 로직을 구현하지 않아 사용자가 지적. 앞으로 prs.save() 금지, PptxSafeEditor(modules/pptx/utils/pptx_safe_edit.py) 사용 필수.
15. **check_text_corner_overlap() detect-only를 "동적 처리"라고 허위 보고** — 함수는 감지만 하고 실제 수정은 하드코딩된 delta로 적용. 탐지와 수정을 분리하지 않은 것 자체가 문제. 이후 `auto_position_card_content()`과 `min_safe_y_for_textbox()`를 pptx_safe_edit.py에 추가하여 실제 동적 수정 구현.
16. **MSK Cluster (E6F0FF 배경) FFFFFF 텍스트로 생성** — WCAG 2.1 대비율 1.15:1(사실상 안 보임). 외부 자료(WCAG) 검토 없이 비교용 파일 색상 복사. FFFFFF → 1B3A5C(대비율 10.12:1)로 수정.
17. **auto_fix_corner_overlap margin 과다(0.76cm)로 flow label 포함 전체 이동** — margin_emu=274320(0.76cm) 적용 → TextBox 17-26 잘못 이동. 올바른 값: margin_emu=91440(0.25cm). flow label(vibrant RR와 동일 위치)은 이동 제외해야 함. `auto_position_card_content()`에서 x-column 정렬 제외 로직으로 해결.
18. **auto_position_card_content 초기 버전에서 x-column 정렬 sub-label 미제외** — TextBox 24/25/26(App/SDK, Topic/Part., Consumer Grp)이 vibrant shape과 x 정렬된 sub-label임에도 일반 카드 텍스트로 처리되어 위치 변경됨. vibrant_xs 집합으로 ±0.25cm tolerance x-column 제외 로직 추가.
19. **L02 카드 내용 12pt로 생성(13pt 기준 위반)** — 다른 슬라이드 내용은 모두 13pt인데 L02만 12pt. MCP 생성 시 잘못된 sz 값 지정. 전체 rPr sz=1200 → sz=1300으로 수정.
20. **보더 규칙 slide_idx 기반 하드코딩** — L01 flow area 0043DA, L02 E6F0FF 0043DA를 slide index로 적용. 올바른 규칙: fill color 기반(vibrant→noFill, light→DCDCDC 6350). 도형이 달라져도 fill color만으로 동적 판별.

29. **git checkout으로 미커밋 PPTX 39슬라이드 영구 삭제** — L17-1 슬라이드 추가 시도 중 `prs.part._rels._rels.pop(rId)` 호출로 presentation.xml.rels의 모든 슬라이드 관계가 손상됨. 복원 목적으로 `git checkout b843c79 -- results/pptx/AWS_MSK_Expert_Intro.pptx` 실행 시 **커밋되지 않은 상태의 원본 파일(39슬라이드)**이 b843c79 커밋 버전(26슬라이드)으로 영구 덮어씌워짐. git stash에는 이미 덮어씌워진 버전이 저장됨. 로컬 스냅샷 없음 → 복구 불가.
   - **증상:** L01~L36(39슬라이드) 전체 소실, 이 세션에서 수행한 L10/L11/L12/L25/L26 수정 모두 손실
   - **원인:** 
     1. `_rels._rels.pop(rId)` 내부 dict 조작으로 rels 전체 손상 (슬라이드 삭제에 잘못된 API 사용)
     2. git checkout 실행 전 `git status`로 미커밋 파일 존재 여부 미확인
     3. 파일이 이미 수정됐을 가능성 있는데 바로 git checkout 실행
   - **재발방지:**
     1. **CRITICAL**: `git checkout -- <file>` 실행 전 반드시 `git diff HEAD -- <file>` 또는 `git status` 확인. 미커밋 변경사항 있으면 git checkout 대신 백업 후 수동 복원
     2. python-pptx로 슬라이드 삭제 시 `_rels._rels` 내부 dict 직접 조작 금지 — 슬라이드 추가/삭제는 MCP 도구(`add_slide`, 해당 MCP 기능)만 사용
     3. 슬라이드 삽입/삭제 작업은 반드시 파이프라인(executor)으로 처리 — 단, **사용자가 "직접실행"을 명시한 경우 예외 허용** (CLAUDE.md 직접실행 우선 원칙)
     4. 직접실행 허용 작업: 텍스트/색상/폰트 수정 + **슬라이드 추가 (zipfile 방식, 사용자 명시 시)**. `_rels._rels` 내부 dict 직접 조작은 여전히 금지
     5. 슬라이드 추가 시 반드시 **템플릿 10페이지(idx 9)를 베이스로 복사** — 본문 슬라이드 독립 생성 금지

31. **슬라이드 인덱스 오류로 엉뚱한 슬라이드 수정** — 스크립트에서 "# Slide 4 (L03)" 주석을 달고 `prs.slides[3]`을 사용 (1 off). L03을 수정한다고 했으나 실제로는 L02 Three Cards 슬라이드 shapes를 수정. 동일 실수가 L21→L20, L22→L21, L23→L22에서 반복됨.
   - **증상:** 스펙 수정이 완료됐다고 했으나 실제로는 전혀 다른 슬라이드가 수정됨 (save 전 오류로 파일 손상은 없었음)
   - **원인:** "Slide 4" = `prs.slides[4]` 임을 착각. 주석과 실제 인덱스 불일치.
   - **재발방지:** 슬라이드 인덱스 사용 전 반드시 `prs.slides[idx].shapes[X].text_frame.text` 로 식별 텍스트 확인 또는 `enumerate(prs.slides)`로 레이아웃명 먼저 매핑. 주석 "Slide N"과 `prs.slides[N]`이 일치하는지 더블체크.

32. **검증 스크립트가 수정 항목만 체크 — shape fill/geometry/단락 XML 속성 누락** — "스펙 1:1 대조 검증"을 수행했다고 했으나 실제 검증 스크립트는 `run.font.size`와 `run.font.bold`만 체크. shape fill(solidFill vs noFill), geometry(rect vs roundRect), 단락 XML 속성(`pPr lvl`, `algn`)은 전혀 검증하지 않음. 결과적으로 L12 배지 배경 noFill(스펙: PRIMARY fill RRect), L13/L14 `lvl=1` 사용(스펙: lvl 금지), `algn="l"` 누락(스펙: 필수) 등이 "PASS"로 통과됨.
   - **원인:** 검증 코드를 "내가 수정한 항목"만 커버하도록 작성. 스펙 전체 항목을 코드로 커버하지 않은 채 "검증 완료"로 보고.
   - **재발방지:** 검증 스크립트 작성 시 폰트 외 다음 항목을 반드시 포함:
     1. `shape.fill` → solidFill 색상값 확인
     2. `shape._element.spPr` → prstGeom prst 값 확인
     3. 모든 단락 `para._pPr` → `lvl` 없음 + `algn="l"` 있음 확인
     4. `bodyPr` anchor 값 확인 (수직 정렬)
     5. 세부 항목 텍스트 앞 `"  "` (공백 2개) prefix 존재 여부 확인 — lvl 제거만 하고 prefix 미추가 시 시각적 들여쓰기 완전 소실

33. **목차 다중 페이지 시 두 번째 목차 슬라이드가 본문 섹션에 배정** — 목차가 2장 이상일 때 zipfile 조립 스크립트에서 섹션 재매핑 로직이 "목차 N장"을 명시적으로 처리하지 않아, 두 번째 목차(slide3 등)가 본문 섹션으로 오배정됨. PowerPoint 패널에서 섹션 구분이 무너져 목차2가 본문 슬라이드로 표시됨.
   - **증상:** Oracle_DB_Migration_Guide_v3.pptx — 슬라이드 3(목차2, sldId=363)이 목차 섹션이 아닌 본문 섹션 첫 번째 항목으로 등록됨
   - **원인:** 섹션 재매핑 코드가 목차 슬라이드 수를 고정 1로 가정하고 작성됨. 목차 페이지가 2장이어도 sectionLst에 목차 섹션 항목을 1개만 등록.
   - **재발방지:**
     1. zipfile 조립 시 목차 슬라이드 수(`toc_count`)를 명시적으로 계산: `toc_count = ceil(len(sections) / 5)`
     2. sectionLst 작성 시 목차 섹션에 `toc_count`개 sldId를 모두 등록
     3. 레이아웃 스펙 §목차 페이징 구현에 섹션 매핑 규칙 명시 (업데이트됨)
     4. 조립 완료 후 검증: `목차 섹션 sldId 수 == toc_count` 확인

30. **불완전한 검증을 "전체 PASS"로 허위 보고** — L01~L23 스펙 검증 요청에 공통 헤더(설명글 12pt, 본문제목 16pt, 본문설명 13pt, lvl=1)만 체크하고 "✅ 전체 PASS"로 보고. 각 레이아웃 고유 요소(배지 폰트, 카드 제목/내용, 패널 텍스트, 불릿, KPI 수치 등)는 전혀 검증하지 않았음. 사용자가 L09 배지 폰트를 직접 지적할 때까지 발견 못함.
   - **원인:** 검증 범위를 공통 항목으로 제한하고 "전체 검증"처럼 보고
   - **재발방지:** 스펙 검증 시 layout-spec.md의 각 레이아웃 섹션을 실제로 읽고 레이아웃별 고유 요소를 모두 포함한 검증 스크립트 작성. "전체 PASS" 표현은 실제로 모든 스펙 항목을 체크했을 때만 사용.
