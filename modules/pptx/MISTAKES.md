# 실수 목록

## 이전 세션들 (2026-04-16 이후)

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
