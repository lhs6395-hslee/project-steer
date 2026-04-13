#!/bin/bash
# Git_Worktree — 병렬 에이전트 실행을 위한 worktree 관리
#
# Usage:
#   bash scripts/agents/git_worktree.sh create <branch_name>
#   bash scripts/agents/git_worktree.sh remove <branch_name>
#   bash scripts/agents/git_worktree.sh merge <branch_name>
#   bash scripts/agents/git_worktree.sh list
#   bash scripts/agents/git_worktree.sh cleanup

set -euo pipefail
trap 'echo "ERROR: Unhandled exception in git_worktree.sh (line $LINENO)" >&2; exit 2' ERRWORKTREE_BASE="../project-steer-worktrees"
ACTION="${1:?Usage: git_worktree.sh <create|remove|merge|list|cleanup> [branch]}"

case "$ACTION" in
  create)
    BRANCH="${2:?create requires branch name}"
    WORKTREE_DIR="$WORKTREE_BASE/$BRANCH"

    if [ -d "$WORKTREE_DIR" ]; then
      echo "Worktree already exists: $WORKTREE_DIR"
      exit 1
    fi

    git worktree add "$WORKTREE_DIR" -b "$BRANCH" 2>/dev/null || \
    git worktree add "$WORKTREE_DIR" "$BRANCH"

    echo "Created worktree: $WORKTREE_DIR (branch: $BRANCH)"
    ;;

  remove)
    BRANCH="${2:?remove requires branch name}"
    WORKTREE_DIR="$WORKTREE_BASE/$BRANCH"

    if [ ! -d "$WORKTREE_DIR" ]; then
      echo "Worktree not found: $WORKTREE_DIR"
      exit 1
    fi

    git worktree remove "$WORKTREE_DIR" --force
    git branch -D "$BRANCH" 2>/dev/null || true
    echo "Removed worktree: $WORKTREE_DIR"
    ;;

  merge)
    BRANCH="${2:?merge requires branch name}"
    WORKTREE_DIR="$WORKTREE_BASE/$BRANCH"

    # 자동 게이트: 머지 전 검증
    echo "Running pre-merge gates on $BRANCH..."

    # JSON 검증
    ERRORS=0
    for f in $(find "$WORKTREE_DIR" -name "*.json" -not -path "*/node_modules/*" 2>/dev/null); do
      if ! python3 -c "import json; json.load(open('$f'))" 2>/dev/null; then
        echo "  ❌ Invalid JSON: $f"
        ERRORS=$((ERRORS + 1))
      fi
    done

    if [ "$ERRORS" -gt 0 ]; then
      echo "Pre-merge gate FAILED: $ERRORS errors"
      exit 1
    fi

    echo "Pre-merge gates passed"

    # 머지
    git merge "$BRANCH" --no-ff -m "Merge agent worktree: $BRANCH"
    echo "Merged $BRANCH into $(git branch --show-current)"

    # 정리
    git worktree remove "$WORKTREE_DIR" --force 2>/dev/null || true
    git branch -D "$BRANCH" 2>/dev/null || true
    echo "Cleaned up worktree: $BRANCH"
    ;;

  list)
    echo "=== Active Worktrees ==="
    git worktree list
    ;;

  cleanup)
    echo "=== Cleaning up all agent worktrees ==="
    if [ -d "$WORKTREE_BASE" ]; then
      for dir in "$WORKTREE_BASE"/*/; do
        branch=$(basename "$dir")
        git worktree remove "$dir" --force 2>/dev/null || true
        git branch -D "$branch" 2>/dev/null || true
        echo "  Removed: $branch"
      done
      rmdir "$WORKTREE_BASE" 2>/dev/null || true
    fi
    echo "Cleanup complete"
    ;;

  *)
    echo "Usage: git_worktree.sh <create|remove|merge|list|cleanup> [branch]"
    exit 1
    ;;
esac
