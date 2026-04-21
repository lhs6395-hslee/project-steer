#!/usr/bin/env bash
# cost_report.sh — Claude Code 세션별 subagent 비용 집계
#
# Usage:
#   bash scripts/cost_report.sh                    # 현재 프로젝트 최신 세션
#   bash scripts/cost_report.sh <session_id>       # 특정 세션
#   bash scripts/cost_report.sh --all              # 현재 프로젝트 전체 세션 합산
#
# 출처: JSONL tool_result 내 total_cost_usd 필드 (Claude Code 내부 기록)
# 환율: 1 USD = 1,380 KRW (고정값, 수동 업데이트 필요)

set -euo pipefail

PROJECT_DIR=$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel 2>/dev/null || echo "$(dirname "$0")/..")
PROJECT_KEY=$(echo "$PROJECT_DIR" | sed 's|/|-|g')
SESSIONS_DIR="$HOME/.claude/projects/$PROJECT_KEY"
KRW_RATE=1380

if [[ ! -d "$SESSIONS_DIR" ]]; then
  echo "ERROR: 세션 디렉토리 없음: $SESSIONS_DIR"
  exit 1
fi

MODE="${1:---latest}"

run_report() {
  local jsonl_file="$1"
  local label="$2"
  python3 - "$jsonl_file" "$label" << 'PYEOF'
import sys, json, re

path = sys.argv[1]
label = sys.argv[2]
KRW_RATE = 1380

total_cost = 0
total_input = 0
total_cache_c = 0
total_cache_r = 0
total_output = 0
results = []

with open(path, 'r', encoding='utf-8') as f:
    for i, raw in enumerate(f):
        raw = raw.strip()
        if not raw: continue
        try:
            d = json.loads(raw)
        except: continue
        content = d.get('message', {}).get('content', [])
        if not isinstance(content, list): continue
        for block in content:
            if not isinstance(block, dict): continue
            if block.get('type') != 'tool_result': continue
            inner = block.get('content', '')
            if not isinstance(inner, str): continue
            if 'total_cost_usd' not in inner: continue

            cost_m = re.search(r'"total_cost_usd"\s*:\s*([0-9.e+-]+)', inner)
            inp_m  = re.search(r'"input_tokens"\s*:\s*([0-9]+)', inner)
            cc_m   = re.search(r'"cache_creation_input_tokens"\s*:\s*([0-9]+)', inner)
            cr_m   = re.search(r'"cache_read_input_tokens"\s*:\s*([0-9]+)', inner)
            out_m  = re.search(r'"output_tokens"\s*:\s*([0-9]+)', inner)
            sid_m  = re.search(r'"session_id"\s*:\s*"([^"]+)"', inner)
            trn_m  = re.search(r'"num_turns"\s*:\s*([0-9]+)', inner)

            if not cost_m: continue

            cost = float(cost_m.group(1))
            inp  = int(inp_m.group(1))  if inp_m  else 0
            cc   = int(cc_m.group(1))   if cc_m   else 0
            cr   = int(cr_m.group(1))   if cr_m   else 0
            out  = int(out_m.group(1))  if out_m  else 0
            sid  = sid_m.group(1)[:8]   if sid_m  else 'N/A'
            trn  = int(trn_m.group(1))  if trn_m  else 0

            total_cost  += cost
            total_input += inp
            total_cache_c += cc
            total_cache_r += cr
            total_output += out
            results.append({'line':i,'cost':cost,'session':sid,'turns':trn,
                            'inp':inp,'cc':cc,'cr':cr,'out':out})

print(f'\n=== {label} ===')
print(f'총 subagent 호출: {len(results)}회')
print()
if results:
    print(f'{"#":>3} {"line":>5} {"session":>10} {"trn":>4} {"input":>8} {"cache_c":>8} {"cache_r":>9} {"output":>8} {"cost_usd":>12}')
    print('-'*85)
    for j, r in enumerate(results, 1):
        print(f'{j:>3} {r["line"]:>5} {r["session"]:>10} {r["turns"]:>4} {r["inp"]:>8} {r["cc"]:>8} {r["cr"]:>9} {r["out"]:>8} ${r["cost"]:>11.6f}')
    print('-'*85)
    print(f'{"합계":>73} ${total_cost:>11.6f}')
    print(f'     input={total_input:,}  cache_c={total_cache_c:,}  cache_r={total_cache_r:,}  output={total_output:,}')
print()
print(f'총 비용: ${total_cost:.4f} USD  ≈ ₩{int(total_cost*KRW_RATE):,}')
PYEOF
}

case "$MODE" in
  --all)
    echo "전체 세션 합산 중..."
    all_cost=0
    for f in "$SESSIONS_DIR"/*.jsonl; do
      [[ -f "$f" ]] || continue
      fname=$(basename "$f" .jsonl)
      run_report "$f" "$fname"
    done
    ;;
  --latest)
    latest=$(ls -t "$SESSIONS_DIR"/*.jsonl 2>/dev/null | head -1)
    if [[ -z "$latest" ]]; then
      echo "ERROR: JSONL 파일 없음"
      exit 1
    fi
    run_report "$latest" "최신 세션: $(basename "$latest" .jsonl)"
    ;;
  *)
    # 특정 session_id
    target="$SESSIONS_DIR/${MODE}.jsonl"
    if [[ ! -f "$target" ]]; then
      echo "ERROR: 세션 파일 없음: $target"
      exit 1
    fi
    run_report "$target" "세션: $MODE"
    ;;
esac
