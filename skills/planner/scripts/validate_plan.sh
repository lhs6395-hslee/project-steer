#!/bin/bash
# Validates that a plan JSON has all required fields and valid structure.
# Usage: bash scripts/validate_plan.sh plan.json

set -euo pipefail

INPUT="${1:?Usage: validate_plan.sh <plan.json>}"

if [ ! -f "$INPUT" ]; then
  echo "ERROR: File not found: $INPUT"
  exit 1
fi

python3 -c "
import json, sys

with open('$INPUT') as f:
    plan = json.load(f)

errors = []

# Required top-level fields
for field in ['task', 'steps', 'acceptance_criteria', 'risks']:
    if field not in plan:
        errors.append(f'Missing required field: {field}')

# Validate steps
if 'steps' in plan:
    if not isinstance(plan['steps'], list):
        errors.append('steps must be a list')
    elif len(plan['steps']) == 0:
        errors.append('steps must not be empty')
    else:
        seen_ids = set()
        for i, step in enumerate(plan['steps']):
            if 'id' not in step:
                errors.append(f'Step {i}: missing id')
            elif step['id'] in seen_ids:
                errors.append(f'Step {i}: duplicate id {step[\"id\"]}')
            else:
                seen_ids.add(step['id'])

            if 'action' not in step:
                errors.append(f'Step {i}: missing action')

            if 'acceptance_criteria' not in step or len(step.get('acceptance_criteria', [])) == 0:
                errors.append(f'Step {i}: must have at least one acceptance criterion')

            # Check circular dependencies
            deps = step.get('dependencies', [])
            if step.get('id') in deps:
                errors.append(f'Step {i}: self-referencing dependency')

if errors:
    print('FAIL:')
    for e in errors:
        print(f'  - {e}')
    sys.exit(1)
else:
    print('PASS: Plan is valid')
"
