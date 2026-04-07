#!/bin/bash
# Validates that a review result JSON has all required fields.
# Usage: bash scripts/validate_review.sh review_result.json

set -euo pipefail

INPUT="${1:?Usage: validate_review.sh <review_result.json>}"

if [ ! -f "$INPUT" ]; then
  echo "ERROR: File not found: $INPUT"
  exit 1
fi

REQUIRED_FIELDS=("verdict" "score" "checklist_results" "issues" "suggestions")
MISSING=()

for field in "${REQUIRED_FIELDS[@]}"; do
  if ! python3 -c "import json,sys; d=json.load(open('$INPUT')); assert '$field' in d" 2>/dev/null; then
    MISSING+=("$field")
  fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
  echo "FAIL: Missing required fields: ${MISSING[*]}"
  exit 1
fi

# Validate verdict value
VERDICT=$(python3 -c "import json; print(json.load(open('$INPUT'))['verdict'])")
if [[ "$VERDICT" != "approved" && "$VERDICT" != "needs_revision" && "$VERDICT" != "rejected" ]]; then
  echo "FAIL: Invalid verdict '$VERDICT'. Must be: approved, needs_revision, rejected"
  exit 1
fi

# Validate score range
python3 -c "
import json, sys
score = json.load(open('$INPUT'))['score']
if not (0.0 <= score <= 1.0):
    print(f'FAIL: Score {score} out of range [0.0, 1.0]')
    sys.exit(1)
"

echo "PASS: Review result is valid"
