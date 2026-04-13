#!/bin/bash
# Auto_Dream — 메모리 파일 자동 정리
# 7일 이상 경과한 완료 Handoff_File을 archive/로 이동
# 중복 엔트리 탐지 및 제거
#
# Usage: bash scripts/agents/auto_dream.sh

set -euo pipefail

source "$(dirname "$0")/ide_adapter.sh"
ensure_agent_dirs

ARCHIVE_DIR="$AGENT_DIR/archive"
DAYS_THRESHOLD=7
MIN_SESSIONS=5
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)

echo "=== Auto_Dream — Memory Cleanup ==="
echo "Timestamp: $TIMESTAMP"
echo "Agent dir: $AGENT_DIR"
echo "Archive threshold: ${DAYS_THRESHOLD} days"

# ── 세션 수 확인 ──
SESSION_COUNT=$(find "$AGENT_DIR" -name "*.json" -not -path "*/archive/*" 2>/dev/null | wc -l | tr -d ' ')
if [ "$SESSION_COUNT" -lt "$MIN_SESSIONS" ]; then
  echo "Only $SESSION_COUNT files found (minimum $MIN_SESSIONS). Skipping cleanup."
  exit 0
fi

# ── 오래된 완료 파일 아카이브 ──
ARCHIVED=0
for dir in requests contracts outputs verdicts results; do
  if [ -d "$AGENT_DIR/$dir" ]; then
    find "$AGENT_DIR/$dir" -name "*.json" -mtime +${DAYS_THRESHOLD} 2>/dev/null | while read -r file; do
      mkdir -p "$ARCHIVE_DIR/$dir"
      mv "$file" "$ARCHIVE_DIR/$dir/"
      ARCHIVED=$((ARCHIVED + 1))
    done
  fi
done

# ── 중복 파일 탐지 ──
DUPLICATES=0
for dir in requests contracts outputs verdicts; do
  if [ -d "$AGENT_DIR/$dir" ]; then
    # MD5 기반 중복 탐지
    find "$AGENT_DIR/$dir" -name "*.json" 2>/dev/null | while read -r file; do
      md5=$(md5 -q "$file" 2>/dev/null || md5sum "$file" 2>/dev/null | cut -d' ' -f1)
      echo "$md5 $file"
    done | sort | uniq -d -w32 | while read -r line; do
      dup_file=$(echo "$line" | cut -d' ' -f2-)
      mkdir -p "$ARCHIVE_DIR/duplicates"
      mv "$dup_file" "$ARCHIVE_DIR/duplicates/"
      DUPLICATES=$((DUPLICATES + 1))
    done
  fi
done

# ── 결과 요약 ──
echo ""
echo "Results:"
echo "  Files scanned: $SESSION_COUNT"
echo "  Archived (>${DAYS_THRESHOLD} days): $ARCHIVED"
echo "  Duplicates removed: $DUPLICATES"
echo "  Archive location: $ARCHIVE_DIR"
