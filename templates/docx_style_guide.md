# DOCX 보고서 표준 서식 가이드

> 신성통상 DB 마이그레이션(재개) 프로젝트의 Word 보고서 작성 시 적용하는 표준 서식.
> 기준 문서: `GWM_운영_컷오버_결과보고서.docx` (XML 분석 기준, 2026-04-01 검증)

---

## 1. 표지 (Cover Page)

표지는 빈 문단 없이 XML spacing(twips)으로 간격을 조절한다.

| 요소 | 서식 | XML spacing |
|------|------|-------------|
| **제목** | 28pt, Bold, `#1A1A2E`, 가운데 정렬 | spBefore=1440, spAfter=240 |
| **부제** | 14pt, `#555555`, 가운데 정렬 | spBefore=160 |
| **날짜** | 14pt, `#555555`, 가운데 정렬, **하단 구분선** | spBefore=80, spAfter=400 |
| **회사명** | 16pt, Bold, 기본 색상, 가운데 정렬 | spBefore=2160, spAfter=0 |
| **구분선** | 날짜 문단의 bottom border (single, sz=4, color=`#CCCCCC`) | — |
| **페이지 브레이크** | 회사명 뒤 빈 문단에 page break → History가 **2페이지**에서 시작 | — |

```
[제목] DMS·Glue 동시 실행 최적화\n보고서  ← 28pt Bold #1A1A2E (줄바꿈은 w:br)
[부제]  ExperDB → Aurora PostgreSQL 마이그레이션  ← 14pt #555555
[날짜]  2026-03-24  ← 14pt #555555 + bottom border #CCCCCC
                    ─────────────────────────────────  ← 구분선 (pBdr bottom)
[회사]  GS네오텍    ← 16pt Bold (spBefore=2160 으로 아래쪽 배치)
[page break]
[History — 2페이지]
```

### 표지 XML 구조 (python-docx)
```python
# 제목 문단
title_p = doc.paragraphs[0]
# spacing: w:spacing w:before="1440" w:after="240"
# alignment: w:jc w:val="center"
# run: w:sz="56" (28pt), w:b, w:color="1A1A2E"
# 줄바꿈: 별도 run에 w:br 요소

# 날짜 문단 — 구분선
# w:pBdr > w:bottom w:val="single" w:sz="4" w:space="1" w:color="CCCCCC"
```

---

## 2. History 테이블

- 위치: **2페이지** (표지 뒤 page break 후)
- Heading 1: "History"
- 테이블: `버전`, `일자`, `작성자`, `내용`
- 작성자: 이홍섭
- History 뒤 page break → 목차 또는 본문

---

## 3. Heading 스타일

| 레벨 | 크기 | 색상 | Bold | 용도 |
|------|------|------|------|------|
| Heading 1 | 14pt | `#1A1A2E` | Yes | 대분류 (`1. 개요`, `2. 타임라인`) |
| Heading 2 | 13pt | `#1A1A2E` | Yes | 소분류 (`1.1 테스트 목적`, `3.1 CPU`) |
| Heading 3 | 12pt | `#1A1A2E` | Yes | 세부 항목 (필요 시) |

- 폰트: `맑은 고딕` (eastAsia: 맑은 고딕)
- Heading 1 앞 spacing: 12pt, 뒤 spacing: 6pt
- **모든 Heading 색상은 `#1A1A2E`로 통일** (레퍼런스 XML 검증 완료)
- **Heading 2에는 반드시 `N.N` 번호를 부여** (예: `1.1 테스트 환경`, `5.1 테스트별 병목 시간 추이`)
- 번호 없는 소제목이 Normal 스타일로 방치되지 않도록 주의

---

## 4. 본문 (Normal)

| 항목 | 값 |
|------|-----|
| 폰트 | 맑은 고딕 |
| 크기 | 10pt |
| 색상 | 기본 (검정) |
| space_after | 4pt |
| space_before | 2pt |

### List Bullet
- 맑은 고딕, 10pt
- 들여쓰기는 기본 Word 불릿 스타일 사용

### 라벨 문단 (Bold)
- 테이블 앞/뒤의 짧은 소제목성 문단은 **Bold** 처리
- 예: **병목 메커니즘:**, **JDBC Write 최적화:**, **19차: DMS 인덱스만 제거**, **20차: DMS + Glue 인덱스 모두 제거**
- Heading 레벨까지는 아니지만, 일반 본문과 구분이 필요한 라벨에 적용

### 테이블 설명 텍스트
- 테이블 바로 아래에 데이터를 해석/설명하는 본문을 작성
- 패턴: `위 표와 같이 ~`, `~이 소요된다.`, `~을 달성한다.` 등
- 테이블만 덩그러니 있으면 페이지가 비어 보이므로 반드시 설명 추가

### 문체
- **현재형 서술체**로 통일: `~한다`, `~이다`, `~을 수행한다`
- `~하였다`, `~었다` (과거형) 사용 금지

---

## 5. 테이블

### 헤더 행
| 항목 | 값 |
|------|-----|
| 배경색 | `#1B3A5C` (navy) |
| 글자색 | `#FFFFFF` (white) |
| 크기 | 9pt |
| Bold | Yes |
| 정렬 | 가운데 |

### 데이터 행
| 항목 | 값 |
|------|-----|
| 배경 (홀수행) | 없음 (흰색) |
| 배경 (짝수행) | `#F2F2F2` (light gray) — zebra striping |
| 크기 | 9pt |
| 정렬 | 가운데 |

### 공통
- 스타일: `Table Grid`
- 테두리: single, sz=4, color=auto (top/left/bottom/right/insideH/insideV)
- 정렬: 가운데 (WD_TABLE_ALIGNMENT.CENTER)

---

## 6. 이미지 (CloudWatch / Datadog 캡처)

### CloudWatch 그래프 (`get-metric-widget-image`)

```bash
aws cloudwatch get-metric-widget-image \
  --profile ssts \
  --region ap-northeast-2 \
  --metric-widget '{
    "metrics": [["AWS/RDS","WriteIOPS","DBInstanceIdentifier","<INSTANCE>",{"stat":"Average","period":300}]],
    "view": "timeSeries",
    "stacked": false,
    "region": "ap-northeast-2",
    "start": "<START_UTC>",
    "end": "<END_UTC>",
    "period": 300,
    "title": "English Title Only",
    "width": 900,
    "height": 400,
    "yAxis": {"left": {"min": 0}}
  }' \
  --output text --query MetricWidgetImage | base64 -d > output.png
```

**주의사항:**
- **제목은 반드시 영문으로 작성** — CloudWatch Widget API가 한글 폰트를 미지원하여 한글이 깨짐 (□□□)
- period: 1분 데이터는 15일 보존, **5분(300)은 63일**, 1시간(3600)은 455일 보존
- 오래된 데이터(15일+)는 `period=300` 이상으로 조회
- 이미지 크기: width=900, height=400 (문서 삽입 시 5.5 inches)

### 주요 메트릭 (개발계정 ssts, 804812023181)

| 서비스 | 메트릭 | Dimension |
|--------|--------|-----------|
| Aurora RDS | WriteIOPS, CPUUtilization, DatabaseConnections, FreeableMemory, WriteThroughput, WriteLatency, CommitLatency | DBInstanceIdentifier=`dev-rds-gwm-cluster-instance-1` |
| DMS | CPUUtilization, FreeableMemory, FreeStorageSpace | ReplicationInstanceIdentifier=`gwm-dms-instance` |

### 주요 메트릭 (운영계정 ssts-prd, 404964886193)

| 서비스 | 메트릭 | Dimension |
|--------|--------|-----------|
| Aurora RDS | 동일 | DBInstanceIdentifier=`prd-rds-gwm-cluster-instance-1` |
| DMS | 동일 | ReplicationInstanceIdentifier=`prd-gwm-dms-instance` |

### Datadog 대시보드 캡처

- Datadog 대시보드 캡처는 브라우저 스크린샷으로 수집
- 대시보드명: `[GS-신성통상] Aurora PostgreSQL GWM Monitoring`
- 캡처 대상: CPU, Memory, Connections, IOPS, Latency, Glue JVM Heap, Executor CPU 등
- 이미지 파일명 규칙: `dd_<metric_name>.png` (예: `dd_cpu_utilization.png`)

### 문서 삽입 규칙

```python
# 이미지 삽입
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run().add_picture(img_path, width=Inches(5.5))

# 캡션 (이미지 바로 아래)
cp = doc.add_paragraph()
cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = cp.add_run('그림 N. 한글 캡션')
r.font.size = Pt(9)
r.font.name = '맑은 고딕'
r.italic = True
```

- 이미지 너비: `Inches(5.5)` 고정
- 캡션: 9pt, 맑은 고딕, 이탤릭, 가운데 정렬
- 번호: `그림 1.`, `그림 2.` 순서대로 전체 문서 기준 연번
- 이미지와 캡션 사이에 빈 문단 없음

---

## 7. 페이지 구성 규칙

| 규칙 | 설명 |
|------|------|
| 표지 → History | **page break** (History는 2페이지에서 시작) |
| History → 목차 | page break |
| 목차 → 본문 | page break |
| 대섹션(Heading 1) 전환 | page break (단, 내용이 적으면 이어서 작성 가능) |
| 섹션 내 여백 | 한 페이지를 가급적 채운 후 넘김 — 반 이상 비어 있으면 내용 보강 |

---

## 8. 푸터 (Footer)

| 항목 | 값 |
|------|-----|
| 내용 | PAGE 필드 (자동 페이지 번호) |
| 정렬 | 가운데 |
| 크기 | 9pt |

```python
# python-docx 푸터 설정
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

for section in doc.sections:
    footer = section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fld = OxmlElement('w:fldSimple')
    fld.set(qn('w:instr'), ' PAGE ')
    r = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')
    sz = OxmlElement('w:sz'); sz.set(qn('w:val'), '18')
    rPr.append(sz)
    r.append(rPr)
    t = OxmlElement('w:t'); t.text = '1'
    r.append(t)
    fld.append(r)
    p._p.append(fld)
```

---

## 9. 색상 팔레트

| 용도 | HEX | RGB | 비고 |
|------|-----|-----|------|
| 제목/Heading 전체 | `#1A1A2E` | (26, 26, 46) | dark navy |
| 부제/날짜 텍스트 | `#555555` | (85, 85, 85) | gray |
| 표지 구분선 | `#CCCCCC` | (204, 204, 204) | light gray border |
| 테이블 헤더 배경 | `#1B3A5C` | (27, 58, 92) | navy |
| 테이블 헤더 글자 | `#FFFFFF` | (255, 255, 255) | white |
| 테이블 짝수행 | `#F2F2F2` | (242, 242, 242) | light gray |

---

## 10. python-docx 코드 템플릿

```python
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

doc = Document()

# ── Style Setup ──
style = doc.styles['Normal']
style.font.name = '맑은 고딕'
style.font.size = Pt(10)
style.element.rPr.rFonts.set(qn('w:eastAsia'), '맑은 고딕')
style.paragraph_format.space_after = Pt(4)
style.paragraph_format.space_before = Pt(2)

HEADINGS = {1: (14, '1A1A2E'), 2: (13, '1A1A2E'), 3: (12, '1A1A2E')}
for lv, (sz, clr) in HEADINGS.items():
    hs = doc.styles[f'Heading {lv}']
    hs.font.size = Pt(sz)
    hs.font.color.rgb = RGBColor.from_string(clr)
    hs.font.bold = True
    hs.font.name = '맑은 고딕'
    hs.element.rPr.rFonts.set(qn('w:eastAsia'), '맑은 고딕')

# ── Cover Page ──
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('보고서 제목')
r.bold = True; r.font.size = Pt(28)
r.font.color.rgb = RGBColor(0x1A, 0x1A, 0x2E)
r.font.name = '맑은 고딕'

# ── Table Helper ──
def add_styled_table(doc, headers, rows):
    t = doc.add_table(rows=1+len(rows), cols=len(headers))
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    # header row
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ''
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True; r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        r.font.name = '맑은 고딕'
        shd = OxmlElement('w:shd')
        shd.set(qn('w:fill'), '1B3A5C')
        shd.set(qn('w:val'), 'clear')
        c._tc.get_or_add_tcPr().append(shd)
    # data rows
    for ri, row_data in enumerate(rows):
        for ci, val in enumerate(row_data):
            c = t.rows[ri+1].cells[ci]
            c.text = ''
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(str(val))
            r.font.size = Pt(9); r.font.name = '맑은 고딕'
            if ri % 2 == 1:  # zebra stripe
                shd = OxmlElement('w:shd')
                shd.set(qn('w:fill'), 'F2F2F2')
                shd.set(qn('w:val'), 'clear')
                c._tc.get_or_add_tcPr().append(shd)
    return t
```

---

## 11. 체크리스트

보고서 완성 시 아래 항목을 확인:

- [ ] 표지 서식: 제목 28pt `#1A1A2E`, 부제 14pt `#555555`, 날짜 14pt `#555555` + 구분선
- [ ] 표지 spacing: title(1440/240), subtitle(160), date(80/400), company(2160/0)
- [ ] 표지 구분선: 날짜 하단 bottom border (single, sz=4, color=`#CCCCCC`)
- [ ] 표지 → History: page break, History는 2페이지
- [ ] History 테이블: 버전/일자/작성자(이홍섭)/내용
- [ ] Heading 색상: `#1A1A2E` 전체 통일 (H1=14pt, H2=13pt, H3=12pt)
- [ ] 테이블 헤더: navy 배경(`#1B3A5C`) + white 글자, 짝수행 `#F2F2F2`
- [ ] 테이블 테두리: Table Grid (single, sz=4)
- [ ] 본문 폰트: 맑은 고딕 10pt
- [ ] 이미지 캡션: 9pt 이탤릭 가운데, `그림 N.` 연번
- [ ] CloudWatch 그래프 제목: 영문만 사용, period≥300 (15일+ 데이터)
- [ ] 페이지 번호: 푸터 가운데, PAGE 필드, 9pt
- [ ] 페이지 채움: 반 이상 빈 페이지 없음 — 테이블 설명 텍스트로 보강
- [ ] page break: 대섹션 전환 시 있음
- [ ] Heading 2 번호: `N.N` 형식 필수 (번호 없는 소제목 금지)
- [ ] 라벨 문단: 테이블 앞뒤 짧은 라벨은 Bold 처리
- [ ] 테이블 설명: 모든 테이블 아래에 데이터 해석 문장 포함
- [ ] 문체: 현재형 `~한다` 통일 (과거형 `~하였다` 금지)
