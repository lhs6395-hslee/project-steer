#!/usr/bin/env bash
# pipeline_cleanup.sh — .pipeline/ 덤프 파일 lifecycle 정리
#
# 기본 정책:
#   - 실행 디렉토리 (20260414T*_pptx 등): 7일 초과 삭제
#   - requests/, suggestions/ 개별 파일:  3일 초과 삭제
#   - archive/, contracts/, metrics/, outputs/, plans/, reports/, results/, verdicts/: 30일 초과 삭제
#   - running.lock, 빈 디렉토리: 유지
#
# 사용법:
#   bash scripts/pipeline_cleanup.sh            # dry-run (삭제 대상만 출력)
#   bash scripts/pipeline_cleanup.sh --execute  # 실제 삭제

set -euo pipefail

PIPELINE_DIR="$(cd "$(dirname "$0")/.." && pwd)/.pipeline"
DRY_RUN=true

[[ "${1:-}" == "--execute" ]] && DRY_RUN=false

if [[ "$DRY_RUN" == "true" ]]; then
  echo "[dry-run] 실제 삭제하려면 --execute 옵션 사용"
fi

delete_target() {
  local target="$1"
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "  [delete] $target"
  else
    rm -rf "$target"
    echo "  deleted: $target"
  fi
}

total=0

# 1. 실행 디렉토리 (타임스탬프 패턴): 7일 초과
echo "── 실행 디렉토리 (>7d) ──"
while IFS= read -r -d '' dir; do
  delete_target "$dir"
  ((total++)) || true
done < <(find "$PIPELINE_DIR" -maxdepth 1 -type d \
  -name "[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]T*" \
  -mtime +7 -print0)

# 2. requests/ 파일: 3일 초과
echo "── requests/ (>3d) ──"
while IFS= read -r -d '' f; do
  delete_target "$f"
  ((total++)) || true
done < <(find "$PIPELINE_DIR/requests" -maxdepth 1 -type f -mtime +3 -print0 2>/dev/null || true)

# 3. suggestions/ 파일: 3일 초과
echo "── suggestions/ (>3d) ──"
while IFS= read -r -d '' f; do
  delete_target "$f"
  ((total++)) || true
done < <(find "$PIPELINE_DIR/suggestions" -maxdepth 1 -type f -mtime +3 -print0 2>/dev/null || true)

# 4. 장기 보관 디렉토리: 30일 초과
for subdir in archive contracts metrics outputs plans reports results verdicts; do
  target="$PIPELINE_DIR/$subdir"
  [[ -d "$target" ]] || continue
  echo "── $subdir/ (>30d) ──"
  while IFS= read -r -d '' f; do
    delete_target "$f"
    ((total++)) || true
  done < <(find "$target" -maxdepth 2 -type f -mtime +30 -print0 2>/dev/null || true)
done

echo ""
if [[ "$DRY_RUN" == "true" ]]; then
  echo "총 삭제 대상: $total 항목 (dry-run — 실제 삭제 없음)"
else
  echo "총 삭제 완료: $total 항목"
fi
